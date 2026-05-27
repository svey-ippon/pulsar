# Cube SQL API & Agent LangGraph — Cas Olist

> Document de référence pour le développement d'un agent LangGraph capable d'interroger un modèle sémantique Cube avec **deux modes** activés après analyse de la complexité de la question par l'agent :
> - **Mode standard** — REST API contre des views métier dédiées (rapide, mise en cache, bénéficie des pré-agrégations).
> - **Mode advanced** — SQL API contre une view exploratoire wide (CTE, window functions, agrégations multi-niveaux).
>
> Version Cube couverte : **Cube Core v1.6.50** (OSS, mai 2026)

---

## Table des matières

1. [La SQL API en deux mots](#1-la-sql-api-en-deux-mots)
2. [Architecture détaillée de la SQL API](#2-architecture-détaillée-de-la-sql-api)
3. [Les trois modes d'exécution](#3-les-trois-modes-dexécution)
4. [Syntaxe SQL acceptée par la SQL API](#4-syntaxe-sql-acceptée-par-la-sql-api)
5. [Authentification](#5-authentification)
6. [Catalogue de questions et stratégie de couverture](#6-catalogue-de-questions-et-stratégie-de-couverture)
7. [Cas d'école Olist — le problème de grain](#7-cas-décole-olist--le-problème-de-grain)
8. [Modèle sémantique Olist recommandé](#8-modèle-sémantique-olist-recommandé)
9. [Résolution des questions standard](#9-résolution-des-questions-standard)
10. [Résolution des questions advanced via SQL API](#10-résolution-des-questions-advanced-via-sql-api)
11. [Design des tools pour l'agent LangGraph](#11-design-des-tools-pour-lagent-langgraph)
12. [Limites et pièges à connaître](#12-limites-et-pièges-à-connaître)

---

## 1. La SQL API en deux mots

La SQL API de Cube expose une interface **PostgreSQL-compatible** où chaque cube ou view du modèle est représenté comme une table, et chaque mesure, dimension ou segment comme une colonne. Sous le capot, elle utilise **Apache DataFusion** comme moteur de requête.

Ce n'est donc **pas du SQL brut vers ta base de données**. Tu écris du SQL, mais contre le **modèle sémantique**. Cube traduit ensuite en SQL vers la source upstream.

Conséquence immédiate pour un agent : la SQL API permet d'exprimer des requêtes que la REST API ne peut pas formuler (CTE, window functions, sous-requêtes, agrégations multi-niveaux) — tout en gardant la gouvernance et la cohérence métier du modèle sémantique. C'est précisément ce dont on a besoin pour résoudre le cas Olist.

---

## 2. Architecture détaillée de la SQL API

### Pile technique

```
┌─────────────────────────────────────┐
│   Client (psql, agent LangGraph)    │
└─────────────┬───────────────────────┘
              │ Wire protocol PostgreSQL
              │ (port CUBEJS_PG_SQL_PORT)
              ▼
┌─────────────────────────────────────┐
│      Cube SQL API (Rust)            │
│  ┌───────────────────────────────┐  │
│  │  Apache DataFusion (planner)  │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  Cube semantic engine         │  │
│  │  (Tesseract pour le SQL gen)  │  │
│  └───────────────────────────────┘  │
└─────────────┬───────────────────────┘
              │ SQL généré (dialecte source)
              ▼
┌─────────────────────────────────────┐
│   Data source (Postgres, BigQuery,  │
│   Snowflake, Databricks, ...)       │
└─────────────────────────────────────┘
```

### Activation

La SQL API est désactivée par défaut. Pour l'activer, définir `CUBEJS_PG_SQL_PORT` :

```bash
# docker-compose.yml / .env
CUBEJS_PG_SQL_PORT=15432
CUBEJS_SQL_USER=cube_agent
CUBEJS_SQL_PASSWORD=*****
```

Connexion ensuite avec n'importe quel client Postgres :

```bash
psql -h localhost -p 15432 -U cube_agent -d cube
```

### Mode streaming pour gros résultats

Par défaut, les résultats sont chargés en un seul batch. Pour les gros volumes, activer le streaming :

```bash
CUBESQL_STREAM_MODE=true
```

En mode streaming, la limite de lignes par défaut ne s'applique plus. Utile pour un agent qui pourrait avoir besoin de scanner des données volumineuses.

### Concurrence

Chaque connexion concurrente consomme des ressources. Pour contrôler :

```bash
CUBEJS_MAX_SESSIONS=100   # défaut variable selon le déploiement
```

Important pour un agent qui pourrait ouvrir plusieurs connexions en parallèle.

---

## 3. Les trois modes d'exécution

La SQL API exécute trois types de requêtes, choisis automatiquement par Cube selon la complexité. Cette distinction est **capitale** pour comprendre les performances et les capacités.

### 3.1 Regular query

C'est l'équivalent SQL d'une requête REST API : une agrégation simple sur un cube/view avec ses mesures et dimensions natives.

```sql
SELECT
  status,
  MEASURE(count),
  MEASURE(total_revenue)
FROM orders
WHERE created_at >= '2024-01-01'
GROUP BY status
```

**Comportement** :
- Cube génère directement le SQL pour la source upstream.
- Bénéficie du **cache in-memory** et des **pré-agrégations**.
- Peut être modifié via `query_rewrite` avant exécution.
- Performance maximale.

**Limite** : tu ne peux faire que ce que la REST API sait faire — pas de CTE, pas de window function, pas d'agrégation sur agrégation.

### 3.2 Query with post-processing

Une regular query est enveloppée dans un FROM ou un CTE, et le reste de la requête est exécuté en mémoire par DataFusion.

```sql
-- La partie interne est une regular query
-- Le AVG externe est exécuté par DataFusion en mémoire
SELECT AVG(count_per_day)
FROM (
  SELECT
    DATE_TRUNC('day', created_at) AS day,
    MEASURE(count) AS count_per_day
  FROM orders
  GROUP BY 1
) AS daily
```

**Comportement** :
- La requête interne est envoyée à la source upstream comme regular query.
- Le post-processing (AVG ici) tourne dans DataFusion, côté Cube.
- Bénéficie aussi du cache et des pré-agrégations sur la partie regular.

**Limite** : seul un sous-ensemble de fonctions/opérateurs SQL est supporté en post-processing (subset de PostgreSQL).

### 3.3 Query with pushdown

Quand la requête a une structure arbitraire (CTE multiples, window functions, joins complexes) qu'on ne peut pas réduire à du post-processing, Cube **transforme la requête entière** et la pousse vers la source upstream.

```sql
-- Ce type de requête utilise le pushdown
WITH ranked AS (
  SELECT
    order_id,
    category,
    ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY total_price DESC) AS rn
  FROM order_items_view
)
SELECT * FROM ranked WHERE rn = 1
```

**Comportement** :
- Pas de pré-agrégations utilisables (la requête est trop spécifique).
- Le cache fonctionne par hash de requête (moins efficace).
- Génère un SQL plus complexe vers la source upstream.
- Active automatiquement les **ungrouped queries** (sans `GROUP BY` forcé).
- Disponible par défaut depuis Cube v1.0.

**Important pour l'agent** : c'est ce mode qui permet de résoudre des requêtes type "Olist". Tu écris ton SQL, Cube le pousse vers la source en respectant les définitions du modèle sémantique.

### Tableau récapitulatif

| Aspect | Regular | Post-processing | Pushdown |
|---|---|---|---|
| Complexité SQL acceptée | Faible | Moyenne | Arbitraire |
| Cache in-memory | ✅ | ✅ (partie regular) | ✅ (par hash) |
| Pré-agrégations | ✅ | ✅ (partie regular) | ❌ |
| `query_rewrite` applicable | ✅ | ✅ | ❌ |
| Performances | Maximales | Bonnes | Variables |
| Use case agent | REST API | Cas intermédiaires | Problèmes de grain/fan-out |

---

## 4. Syntaxe SQL acceptée par la SQL API

### Mesures avec `MEASURE()`

La fonction spéciale `MEASURE()` fonctionne avec n'importe quel type de mesure :

```sql
SELECT MEASURE(count), MEASURE(avg_review_score) FROM reviews
```

On peut aussi utiliser les fonctions d'agrégation natives **si elles matchent le type de la mesure** :

```sql
-- ✅ count est de type count
SELECT COUNT(count) FROM orders

-- ✅ total_revenue est de type sum
SELECT SUM(total_revenue) FROM orders

-- ❌ Ne marche pas : avg_score est de type avg, on ne peut pas le re-AVG
SELECT AVG(avg_score) FROM reviews
```

### `COUNT(*)` spécial

Dans les requêtes post-processing, `COUNT(*)` est traduit par Cube vers la **première mesure de type `count`** du cube référencé. Comportement à connaître pour éviter les surprises.

### Functions et opérateurs

La SQL API implémente un **sous-ensemble** des fonctions et opérateurs PostgreSQL. Les classiques fonctionnent :

- `WHERE`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`, `OFFSET`
- `CROSS JOIN`, `INNER JOIN` (entre cubes joints dans le modèle)
- Sous-requêtes dans `FROM` et CTE (`WITH`)
- Window functions (`ROW_NUMBER`, `RANK`, `LAG`, `LEAD`, `OVER`...)
- Fonctions classiques : `COALESCE`, `NULLIF`, `CASE`, `EXTRACT`, `DATE_TRUNC`...

### Commandes utiles

```sql
-- Voir le plan d'exécution
EXPLAIN SELECT MEASURE(count) FROM orders;

-- Lister les cubes/views disponibles (équivalent psql)
\dt

-- Décrire un cube
\d orders
```

---

## 5. Authentification

### 5.1 Pour le POC : authentification simple par compte technique

Cube vérifie par défaut nom d'utilisateur et mot de passe via deux variables d'environnement :

```bash
CUBEJS_SQL_USER=cube_agent
CUBEJS_SQL_PASSWORD=<strong-password>
```

L'agent LangGraph utilise alors une chaîne de connexion classique :

```
postgresql://cube_agent:<password>@cube-host:15432/cube
```

C'est le mode recommandé pour démarrer un POC. Pas de multi-tenant, pas de row-level security : tous les utilisateurs (ici, l'agent) voient la même chose.

### 5.2 Aller plus loin : JWT + security context

Pour une production réelle, Cube supporte une authentification **JWT** avec **security context**, qui ouvre beaucoup de portes.

**Principe** :
1. Un serveur d'auth (Auth0, Keycloak, ton propre service) émet un JWT signé.
2. Le client (l'agent) passe le JWT dans le header `Authorization`.
3. Cube vérifie la signature via JWKS (ou clé partagée) et **injecte les claims du token dans le security context**.
4. Le security context est ensuite utilisable dans :
   - les **access policies** YAML (row-level + member-level security),
   - les **mesures et dimensions dynamiques** via `COMPILE_CONTEXT`,
   - le `query_rewrite` côté serveur,
   - le `checkSqlAuth` pour authentification SQL API custom.

**Exemple JWT pour SQL API** :
```json
{
  "sub": "user_42",
  "role": "analyst",
  "tenant_id": "olist_fr",
  "iat": 1700000000,
  "exp": 1700086400
}
```

**Configuration côté Cube** (`cube.js` / `cube.py`) :
```javascript
module.exports = {
  jwt: {
    jwkUrl: 'https://my-auth.example.com/.well-known/jwks.json',
    audience: 'cube-api',
    issuer: ['https://my-auth.example.com/']
  },

  // Custom auth pour SQL API
  checkSqlAuth: async (req, user, password) => {
    // Validation custom du couple user/password ou du token
    return { password, securityContext: { /* ... */ } }
  },

  // Permettre à certains users de "switcher" de security context
  // (utile pour un agent qui agirait au nom de plusieurs utilisateurs)
  canSwitchSqlUser: async (current, requested) => {
    return current === 'cube_agent_supervisor'
  }
}
```

**Pour aller plus loin**, voici les axes :

| Capacité | À explorer |
|---|---|
| Multi-tenant strict | `contextToAppId` (un appId par tenant → cache et pré-agrégations isolés) |
| Row-level security | `access_policy` YAML avec `row_level.filters` référençant `COMPILE_CONTEXT.securityContext` |
| Member-level security | `access_policy` YAML avec `member_level.includes` / `excludes` |
| Filtres dynamiques transparents | `queryRewrite` côté serveur (ajout automatique de filtres aux requêtes) |
| Modèles dynamiques par tenant | `schemaVersion` + `repositoryFactory` (modèle compilé différemment par contexte) |
| Délégation d'identité (agent → user) | `canSwitchSqlUser` + `SET SQL_USER` au runtime |

### 5.3 Recommandation pour ton POC

Démarre simple :
- Compte technique unique pour l'agent.
- Pas de security context.
- Le modèle est entièrement visible par l'agent.

Quand tu passeras en prod ou en multi-tenant :
- Génère un JWT par session utilisateur.
- L'agent transmet le JWT en `Authorization` lors de chaque appel.
- Tu définis des `access_policy` YAML sur les cubes sensibles.
- Le row-level filtering devient déclaratif et auditable.

---

## 6. Catalogue de questions et stratégie de couverture

Le tableau ci-dessous présente le panel de questions que l'agent doit savoir traiter, avec le mode attendu et la justification du routage. C'est ce panel qui pilote la conception des views du modèle sémantique.

### Tableau de couverture

| # | Question | Mode | View cible | Pourquoi ce mode |
|---|---|---|---|---|
| 1 | How many orders are in the database? | STANDARD | `orders_overview` | Comptage simple sur une mesure native |
| 2 | How many customers are based in São Paulo state? | STANDARD | `orders_overview` | Comptage + filtre sur dimension |
| 3 | What are the 5 most-used payment methods? | STANDARD | `payments_overview` | Group by + order by + limit |
| 4 | What is the average review score across all reviews? | STANDARD | `reviews_overview` | Mesure native (`avg_score`) du modèle |
| 5 | What is the total value collected across all orders? | STANDARD | `payments_overview` ou `catalog_sales` | Somme native — ⚠️ ambiguïté : GMV (items.price) vs encaissé (payments.value). L'agent doit choisir une convention et la communiquer |
| 6 | What are the top 10 product categories by total revenue? (EN names) | STANDARD | `catalog_sales` | Group by + order + limit, sur dimension déjà en anglais dans la view |
| 7 | Show monthly revenue for 2017 | STANDARD | `orders_overview` ou `catalog_sales` | Time dimension + filtre |
| 8 | What share of payments are paid in more than one installment? | STANDARD | `payments_overview` | Deux mesures (`count_total`, `count_multi_installment`), ratio post-process côté agent |
| 9 | How many orders are paid in more than one installment? | STANDARD | `payments_overview` | Mesure filtrée native |
| 10 | Who are our best sellers? (by revenue) | STANDARD | `catalog_sales` | Group by seller + sum, après désambiguïsation de "best" |
| 11 | Top 3 seller states (revenue per seller, 2017, states with > 5 sellers) | **ADVANCED** | `olist_explorer` | HAVING sur agrégat (>5 sellers) + ratio sur deux agrégats groupés (revenue / nb sellers) + ranking. Pas exprimable en REST. |
| 12 | Avg review score by category, categories with ≥ 50 reviews (EN) | **ADVANCED** | `olist_explorer` | Problème de grain (review = order, category = item) + HAVING sur agrégat. Voir §7 pour l'analyse détaillée. |
| 13 | Top 3 product categories by revenue within each customer state | **ADVANCED** | `olist_explorer` | Window function (`ROW_NUMBER() OVER (PARTITION BY state ORDER BY revenue DESC)`) |
| 14 | 2017 cohorts: % of customers who made a 2nd purchase within 90 days | **ADVANCED** | `olist_explorer` | Self-join temporel, cohort analysis, comparaison entre premier et deuxième achat par customer |
| 15 | Seller states with worst avg delivery performance (≥ 100 deliveries) | **ADVANCED** | `olist_explorer` | HAVING sur agrégat (≥100). Filtrage manuel post-process possible mais fragile à grande échelle |
| 16 | Late deliveries vs review score (on-time vs late) | **STANDARD** | `orders_overview` ou `reviews_overview` | Possible en standard **grâce à la dimension `delivery_status`** ajoutée au modèle (voir §8). Sans cette dimension, serait advanced. |
| 17 | Revenue share: repeat customers (2+ orders) vs one-time customers | **ADVANCED** | `olist_explorer` | Classification client basée sur l'historique = sub-query ou window + agrégation. Modéliser `is_repeat_customer` figerait trop de logique métier. |

### Bilan

- **11 questions en standard** sur 17 (65%) — bénéficient du cache et des pré-agrégations.
- **6 questions en advanced** — toutes liées à des problèmes structurels : window functions, HAVING sur agrégat, problèmes de grain, ou logique de classification client.

### Principes du routing

L'agent décide du mode au moment du **planning** de la requête, en s'appuyant sur ces signaux :

| Signal dans la question | Indication |
|---|---|
| Pas de comparaison entre niveaux d'agrégation | STANDARD probable |
| "By X" où X est une dimension directe dans une view | STANDARD |
| Filtre sur un agrégat ("at least N", "more than X") | ADVANCED |
| Ranking / top-N par groupe ("top X within each Y") | ADVANCED (window) |
| Classification client/produit basée sur historique | ADVANCED |
| Croisement de grains incompatibles | ADVANCED (voir §7) |

Le tableau de couverture ci-dessus sert aussi de **dataset d'évaluation** pour le POC : tester chaque question, vérifier que l'agent route correctement et obtient le bon résultat.

---

## 7. Cas d'école Olist — le problème de grain

Plusieurs questions du catalogue ci-dessus illustrent un même problème structurel : **le mismatch de granularité entre deux entités**. La question 12 ("avg review score by category") en est l'archétype et sert de fil rouge dans la suite du document.

### La question métier

> *What is the average review score by product category, for categories with at least 50 reviews? Use English names.*

### Pourquoi c'est non-trivial

Le dataset Olist (Kaggle e-commerce brésilien) présente une structure relationnelle classique d'e-commerce :

```
order_reviews ──┐
                │
                ▼
              orders ──→ order_items ──→ products ──→ category_translations
                                                       (PT → EN)
```

Deux difficultés s'opposent à une réponse directe :

**1. Problème de grain (granularité)**
- Une `review` est attachée à un `order` (1 review = 1 order).
- Une `category` est attachée à un `product`, donc à un `order_item` (1 order peut contenir N items de M catégories).

**Question implicite** : à quelle catégorie attribuer la review d'un order qui contient plusieurs catégories ?

**2. Fan-out**
Si tu joins naïvement `reviews → orders → order_items → products → categories`, une review d'un order avec 3 items est multipliée par 3 dans le résultat. Si tu fais ensuite `AVG(review_score)`, tu pondères artificiellement par le nombre d'items.

### La requête SQL de référence

Une stratégie raisonnable consiste à attribuer chaque order à sa **catégorie dominante** (la catégorie avec le plus d'items, départagée par prix total).

```sql
WITH order_category AS (
    SELECT
        oi.order_id,
        pct.product_category_name_english,
        COUNT(*) AS item_count,
        SUM(oi.price) AS total_price
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    JOIN product_category_name_translation pct
        ON p.product_category_name = pct.product_category_name
    GROUP BY oi.order_id, pct.product_category_name_english
),
order_dominant_category AS (
    SELECT
        order_id,
        product_category_name_english,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY item_count DESC, total_price DESC
        ) AS rn
    FROM order_category
),
order_with_category AS (
    SELECT order_id, product_category_name_english
    FROM order_dominant_category
    WHERE rn = 1
),
reviews_with_category AS (
    SELECT
        owc.product_category_name_english,
        r.review_score
    FROM order_reviews r
    JOIN order_with_category owc ON r.order_id = owc.order_id
)
SELECT
    product_category_name_english AS category,
    COUNT(*) AS review_count,
    ROUND(AVG(review_score), 2) AS avg_review_score
FROM reviews_with_category
GROUP BY product_category_name_english
HAVING COUNT(*) >= 50
ORDER BY avg_review_score DESC;
```

Cette requête combine **CTE multiples**, **window function** (`ROW_NUMBER`), **HAVING** sur agrégat — précisément ce que la REST API de Cube ne sait pas exprimer. Elle est résolue via la SQL API en §10.

---

## 8. Modèle sémantique Olist recommandé

### Principes appliqués

1. **Tous les cubes en `public: false`** — invisibles depuis la SQL API et la REST API directement.
2. **Toutes les expositions passent par des views** — gouvernance et chemins de join contrôlés.
3. **Primary keys déclarées partout** — obligatoire pour les joins et les pré-agrégations.
4. **Joins déclarés du côté "fact"** vers le côté "dim" (many_to_one).
5. **Une view exploratoire wide** (`olist_explorer`) + **4 views métier ciblées** maximisant la couverture en mode standard.

### Structure de fichiers

```
model/
├── cubes/
│   ├── orders/
│   │   ├── orders.yml
│   │   ├── order_items.yml
│   │   └── order_reviews.yml
│   ├── catalog/
│   │   ├── products.yml
│   │   ├── sellers.yml
│   │   └── product_category_translations.yml
│   └── customers/
│       └── customers.yml
└── views/
    ├── exploration/
    │   └── olist_explorer.yml      # ← view large pour l'agent
    └── metrics/
        ├── reviews_by_category.yml # ← view métier ciblée
        └── revenue_by_category.yml
```

### Définition des cubes

**`cubes/orders/orders.yml`**

```yaml
cubes:
  - name: orders
    sql_table: public.orders
    public: false
    description: "Commandes Olist (fait principal côté order)"

    joins:
      - name: customers
        sql: "{CUBE}.customer_id = {customers.customer_id}"
        relationship: many_to_one

    dimensions:
      - name: order_id
        sql: order_id
        type: string
        primary_key: true

      - name: customer_id
        sql: customer_id
        type: string
        public: false

      - name: status
        sql: order_status
        type: string

      - name: purchased_at
        sql: order_purchase_timestamp
        type: time

      - name: approved_at
        sql: order_approved_at
        type: time

      - name: delivered_at
        sql: order_delivered_customer_date
        type: time

      - name: estimated_delivery_at
        sql: order_estimated_delivery_date
        type: time

      # ─── Dimensions calculées : enrichissement du modèle ───
      # Ces dimensions transforment des questions ADVANCED en STANDARD
      # en encapsulant une logique métier simple directement dans le cube.

      - name: delay_days
        sql: >
          DATE_PART('day',
            {CUBE}.order_delivered_customer_date
            - {CUBE}.order_estimated_delivery_date
          )
        type: number
        description: >
          Nombre de jours de retard à la livraison (négatif si en avance).
          NULL si la commande n'est pas encore livrée.

      - name: delivery_status
        sql: >
          CASE
            WHEN {CUBE}.order_delivered_customer_date IS NULL THEN 'not_delivered'
            WHEN {CUBE}.order_delivered_customer_date
                 <= {CUBE}.order_estimated_delivery_date THEN 'on_time'
            WHEN {CUBE}.order_delivered_customer_date
                 <= {CUBE}.order_estimated_delivery_date + INTERVAL '7 days' THEN 'late'
            ELSE 'very_late'
          END
        type: string
        description: >
          Statut de livraison vs date estimée :
          'on_time' (livré à temps), 'late' (jusqu'à 7j de retard),
          'very_late' (plus de 7j de retard), 'not_delivered' (en cours).

      - name: is_delivered
        sql: "{CUBE}.order_delivered_customer_date IS NOT NULL"
        type: boolean

    measures:
      - name: count
        type: count
        description: "Nombre de commandes distinctes"

      - name: avg_delay_days
        sql: "{delay_days}"
        type: avg
        description: "Délai moyen de livraison vs date estimée — ⚠️ non-additive"

      - name: delivered_count
        sql: order_id
        type: count
        filters:
          - sql: "{CUBE}.order_delivered_customer_date IS NOT NULL"
```

**`cubes/orders/order_items.yml`**

```yaml
cubes:
  - name: order_items
    sql_table: public.order_items
    public: false
    description: "Lignes de commande (1 row = 1 produit dans une commande)"

    joins:
      - name: orders
        sql: "{CUBE}.order_id = {orders.order_id}"
        relationship: many_to_one

      - name: products
        sql: "{CUBE}.product_id = {products.product_id}"
        relationship: many_to_one

      - name: sellers
        sql: "{CUBE}.seller_id = {sellers.seller_id}"
        relationship: many_to_one

    dimensions:
      # Clé composite : un item est identifié par (order_id, order_item_id)
      - name: order_id
        sql: order_id
        type: string
        primary_key: true

      - name: order_item_id
        sql: order_item_id
        type: number
        primary_key: true

      - name: product_id
        sql: product_id
        type: string
        public: false

      - name: seller_id
        sql: seller_id
        type: string
        public: false

      - name: shipping_limit_date
        sql: shipping_limit_date
        type: time

    measures:
      - name: count
        type: count
        description: "Nombre de lignes de commande"

      - name: total_price
        sql: price
        type: sum
        format: currency

      - name: total_freight
        sql: freight_value
        type: sum
        format: currency
```

**`cubes/orders/order_reviews.yml`**

```yaml
cubes:
  - name: order_reviews
    sql_table: public.order_reviews
    public: false
    description: "Avis clients (1 review = 1 order, parfois plusieurs par order si édition)"

    joins:
      - name: orders
        sql: "{CUBE}.order_id = {orders.order_id}"
        relationship: many_to_one

    dimensions:
      - name: review_id
        sql: review_id
        type: string
        primary_key: true

      - name: order_id
        sql: order_id
        type: string
        public: false

      - name: score
        sql: review_score
        type: number

      - name: created_at
        sql: review_creation_date
        type: time

      - name: answered_at
        sql: review_answer_timestamp
        type: time

    measures:
      - name: count
        type: count
        description: "Nombre de reviews"

      - name: avg_score
        sql: review_score
        type: avg
        description: "Note moyenne — ⚠️ non-additive, ne pas pré-agréger"
```

**`cubes/catalog/products.yml`**

```yaml
cubes:
  - name: products
    sql_table: public.products
    public: false
    description: "Catalogue produits"

    joins:
      - name: product_category_translations
        sql: "{CUBE}.product_category_name = {product_category_translations.category_name_pt}"
        relationship: many_to_one

    dimensions:
      - name: product_id
        sql: product_id
        type: string
        primary_key: true

      - name: category_name_pt
        sql: product_category_name
        type: string
        public: false   # version portugaise — on préfère l'anglaise côté view

      - name: weight_g
        sql: product_weight_g
        type: number

      - name: photos_qty
        sql: product_photos_qty
        type: number

    measures:
      - name: count
        type: count
```

**`cubes/catalog/product_category_translations.yml`**

```yaml
cubes:
  - name: product_category_translations
    sql_table: public.product_category_name_translation
    public: false
    description: "Traductions PT → EN des catégories"

    dimensions:
      - name: category_name_pt
        sql: product_category_name
        type: string
        primary_key: true
        public: false

      - name: category_name
        sql: product_category_name_english
        type: string
        title: "Product Category"
```

**`cubes/customers/customers.yml`**

```yaml
cubes:
  - name: customers
    sql_table: public.customers
    public: false
    description: "Clients Olist (1 row par customer_id, qui est un identifiant par commande dans Olist)"

    dimensions:
      - name: customer_id
        sql: customer_id
        type: string
        primary_key: true

      - name: customer_unique_id
        sql: customer_unique_id
        type: string
        description: "Identifiant unique stable du client à travers ses commandes"

      - name: city
        sql: customer_city
        type: string

      - name: state
        sql: customer_state
        type: string
        title: "Customer State"

      - name: zip_code
        sql: customer_zip_code_prefix
        type: string

    measures:
      - name: count
        type: count
        description: "Nombre de customer_id (≈ nombre d'orders)"

      - name: count_unique
        sql: customer_unique_id
        type: count_distinct
        description: "Nombre de clients uniques — ⚠️ non-additive"
```

**`cubes/catalog/sellers.yml`**

```yaml
cubes:
  - name: sellers
    sql_table: public.sellers
    public: false
    description: "Vendeurs Olist"

    dimensions:
      - name: seller_id
        sql: seller_id
        type: string
        primary_key: true

      - name: city
        sql: seller_city
        type: string

      - name: state
        sql: seller_state
        type: string
        title: "Seller State"

      - name: zip_code
        sql: seller_zip_code_prefix
        type: string

    measures:
      - name: count
        type: count
        description: "Nombre de vendeurs"
```

**`cubes/orders/order_payments.yml`**

```yaml
cubes:
  - name: order_payments
    sql_table: public.order_payments
    public: false
    description: >
      Paiements des commandes. ⚠️ Plusieurs paiements possibles par order
      (1 carte + 1 voucher par exemple). Primary key composite.

    joins:
      - name: orders
        sql: "{CUBE}.order_id = {orders.order_id}"
        relationship: many_to_one

    dimensions:
      - name: order_id
        sql: order_id
        type: string
        primary_key: true

      - name: payment_sequential
        sql: payment_sequential
        type: number
        primary_key: true

      - name: payment_type
        sql: payment_type
        type: string
        title: "Payment Method"

      - name: installments
        sql: payment_installments
        type: number

      - name: is_multi_installment
        sql: "{CUBE}.payment_installments > 1"
        type: boolean

    measures:
      - name: count
        type: count
        description: "Nombre de paiements"

      - name: total_value
        sql: payment_value
        type: sum
        format: currency
        description: "Valeur totale encaissée"

      - name: count_multi_installment
        sql: order_id
        type: count
        filters:
          - sql: "{CUBE}.payment_installments > 1"
        description: "Nombre de paiements en plusieurs fois"

      - name: avg_installments
        sql: payment_installments
        type: avg
        description: "Nombre moyen d'échéances — ⚠️ non-additive"
```

### Définition des views

Cinq views sont définies : **4 views métier** ciblées pour le mode standard, et **1 view exploratoire wide** pour le mode advanced via SQL API.

#### `views/exploration/olist_explorer.yml` — view wide pour le mode ADVANCED

```yaml
views:
  - name: olist_explorer
    description: >
      Vue exploratoire dénormalisée du dataset Olist.
      Cible : SQL API en mode ADVANCED pour requêtes complexes
      (CTE, window functions, problèmes de grain).
      Permet de naviguer entre orders, items, reviews, products, categories,
      sellers, customers, payments.

    cubes:
      - join_path: orders
        includes:
          - order_id
          - status
          - purchased_at
          - delivered_at
          - estimated_delivery_at
          - delivery_status
          - delay_days
          - is_delivered
          - count

      - join_path: orders.customers
        prefix: true
        includes:
          - customer_unique_id
          - state
          - city
          - count
          - count_unique

      - join_path: orders.order_items
        prefix: true
        includes:
          - order_item_id
          - count
          - total_price
          - total_freight

      - join_path: orders.order_items.products
        prefix: true
        includes:
          - product_id
          - weight_g
          - photos_qty

      - join_path: orders.order_items.products.product_category_translations
        includes:
          - category_name

      - join_path: orders.order_items.sellers
        prefix: true
        includes:
          - seller_id
          - state
          - city
          - count

      - join_path: orders.order_reviews
        prefix: true
        includes:
          - review_id
          - score
          - count
          - avg_score
          - created_at

      - join_path: orders.order_payments
        prefix: true
        includes:
          - payment_type
          - installments
          - is_multi_installment
          - count
          - total_value
```

#### `views/metrics/orders_overview.yml` — view métier (mode STANDARD)

```yaml
views:
  - name: orders_overview
    description: >
      Vue centrée sur les commandes : volume, statut, performance de livraison,
      contexte client (état, ville). Couvre les questions sur le nombre de
      commandes, la performance de livraison, et la satisfaction par état.
    meta:
      example_questions:
        - "How many orders are in the database?"
        - "How many customers are in São Paulo state?"
        - "Show monthly revenue for 2017"
        - "How do late deliveries affect customer satisfaction?"

    cubes:
      - join_path: orders
        includes:
          - order_id
          - status
          - purchased_at
          - delivered_at
          - delivery_status
          - delay_days
          - is_delivered
          - count
          - delivered_count
          - avg_delay_days

      - join_path: orders.customers
        includes:
          - state
          - city
          - count_unique

      - join_path: orders.order_reviews
        includes:
          - score
          - avg_score
          - count
```

#### `views/metrics/payments_overview.yml` — view métier (mode STANDARD)

```yaml
views:
  - name: payments_overview
    description: >
      Vue centrée sur les paiements : montants, méthodes, échéances.
      Couvre les questions sur les méthodes de paiement, la valeur totale
      encaissée, et la part de paiements en plusieurs fois.
    meta:
      example_questions:
        - "What are the 5 most-used payment methods?"
        - "What is the total value collected across all orders?"
        - "What share of payments are paid in more than one installment?"

    cubes:
      - join_path: order_payments
        includes:
          - payment_type
          - installments
          - is_multi_installment
          - count
          - total_value
          - count_multi_installment
          - avg_installments

      - join_path: order_payments.orders
        includes:
          - purchased_at
          - status
```

#### `views/metrics/catalog_sales.yml` — view métier (mode STANDARD)

```yaml
views:
  - name: catalog_sales
    description: >
      Vue centrée sur les ventes au grain ITEM : revenus, catégories,
      vendeurs, produits. Couvre les questions sur le top des catégories,
      les meilleurs vendeurs, et le revenu par produit ou par état de vendeur.
    meta:
      example_questions:
        - "What are the top 10 product categories by total revenue?"
        - "Who are our best sellers by revenue?"
        - "Show monthly revenue for 2017"

    cubes:
      - join_path: order_items
        includes:
          - count
          - total_price
          - total_freight

      - join_path: order_items.orders
        includes:
          - purchased_at
          - status

      - join_path: order_items.products
        includes:
          - product_id

      - join_path: order_items.products.product_category_translations
        includes:
          - category_name

      - join_path: order_items.sellers
        prefix: true
        includes:
          - seller_id
          - state
          - city
```

#### `views/metrics/reviews_overview.yml` — view métier (mode STANDARD)

```yaml
views:
  - name: reviews_overview
    description: >
      Vue centrée sur les reviews au grain ORDER : score moyen, distribution
      des notes, croisement avec performance de livraison et état client.
      ⚠️ Ne contient PAS la catégorie produit (problème de grain — utiliser
      olist_explorer en mode advanced pour cela).
    meta:
      example_questions:
        - "What is the average review score across all reviews?"
        - "How do late deliveries affect satisfaction?"
        - "Average review score by customer state"

    cubes:
      - join_path: order_reviews
        includes:
          - score
          - created_at
          - count
          - avg_score

      - join_path: order_reviews.orders
        includes:
          - status
          - purchased_at
          - delivery_status
          - delay_days

      - join_path: order_reviews.orders.customers
        includes:
          - state
          - city
```

### Récapitulatif de couverture standard

| View | Questions couvertes |
|---|---|
| `orders_overview` | Q1, Q2, Q7, Q16 |
| `payments_overview` | Q3, Q5 (variante encaissé), Q8, Q9 |
| `catalog_sales` | Q5 (variante GMV), Q6, Q7, Q10 |
| `reviews_overview` | Q4, Q16 |
| `olist_explorer` | Q11, Q12, Q13, Q14, Q15, Q17 (advanced) |

### Note sur `example_questions`

Le champ `meta.example_questions` est un **ajout pour le POC** dont l'objectif est d'aider le LLM à matcher question utilisateur → bonne view. **Tester d'abord sans ce champ** pour évaluer les capacités réelles du LLM à partir de la `description` seule. Si le routing échoue trop souvent, activer le champ et mesurer l'amélioration. Cube ne traite pas spécifiquement ce champ — il est exposé via la REST API `/v1/meta` et c'est à l'outil `describe_view` de le surfacer.

### Bonnes pratiques production additionnelles

Pour un modèle Olist en production, au-delà de ce qui est ci-dessus :

1. **Cube intermédiaire `order_dominant_category`** matérialisant la règle "catégorie dominante" en SQL, avec primary key `order_id`. Joinable depuis `order_reviews`. Évite que chaque consommateur réinvente la règle, et fait passer Q12 en mode standard.
2. **Pré-agrégations** sur les views métier critiques (`orders_overview`, `catalog_sales`) partitionnées par mois sur `purchased_at`.
3. **Hierarchies** déclarées sur les dimensions temporelles (year → quarter → month → day) pour le drill-down BI.
4. **Access policies** par tenant si le dataset est partagé (ex: par seller).
5. **Tests d'intégrité** : query de check que `COUNT(DISTINCT orders.order_id)` est stable quelles que soient les dimensions ajoutées (non-régression sur les joins).
6. **Mesures de ratio matérialisées** : pour Q8 (`share_multi_installment`), un modèle production définirait cette mesure directement plutôt que de laisser l'agent calculer le ratio. Décision arbitrée selon le ratio "flexibilité agent" vs "cohérence métier".

---

## 9. Résolution des questions standard

Cette section illustre comment l'agent utilise la **REST API** contre les **views métier** pour répondre aux 11 questions de mode standard. Chaque exemple montre la sélection de view, les mesures/dimensions/filtres, et la query générée.

Toutes ces requêtes passent par `query_view` (REST `/v1/load`) et bénéficient du cache in-memory et des pré-agrégations.

### Q1 — How many orders are in the database?

```yaml
view: orders_overview
measures: [orders.count]
```

### Q2 — How many customers are based in São Paulo state?

```yaml
view: orders_overview
measures: [customers.count_unique]
filters:
  - member: customers.state
    operator: equals
    values: [SP]
```

> Note : `customers.count_unique` car `customers.count` compte les `customer_id` (≈ orders), pas les clients réels. C'est typiquement le genre d'ambiguïté qui mérite un commentaire dans `describe_view`.

### Q3 — Top 5 most-used payment methods

```yaml
view: payments_overview
measures: [order_payments.count]
dimensions: [order_payments.payment_type]
order:
  order_payments.count: desc
limit: 5
```

### Q4 — Average review score across all reviews

```yaml
view: reviews_overview
measures: [order_reviews.avg_score]
```

### Q5 — Total value collected across all orders

Cas ambigu, deux interprétations possibles. L'agent doit choisir et communiquer son choix :

```yaml
# Variante "encaissé" (sum des paiements)
view: payments_overview
measures: [order_payments.total_value]
```

```yaml
# Variante "GMV" (sum des prix items, hors freight)
view: catalog_sales
measures: [order_items.total_price]
```

### Q6 — Top 10 product categories by total revenue (EN names)

```yaml
view: catalog_sales
measures: [order_items.total_price]
dimensions: [product_category_translations.category_name]
order:
  order_items.total_price: desc
limit: 10
```

### Q7 — Monthly revenue for 2017

```yaml
view: catalog_sales
measures: [order_items.total_price]
time_dimensions:
  - dimension: orders.purchased_at
    granularity: month
    date_range: ['2017-01-01', '2017-12-31']
```

### Q8 — Share of payments paid in more than one installment

Deux mesures retournées, ratio calculé côté agent (post-process) :

```yaml
view: payments_overview
measures:
  - order_payments.count
  - order_payments.count_multi_installment
```

L'agent calcule ensuite `count_multi_installment / count` et formate en pourcentage. **Avantage** : flexibilité (l'agent peut faire des variantes : par méthode de paiement, par mois, etc.) sans recoder le modèle. **Inconvénient** : ratio non disponible directement dans BI tools.

### Q9 — How many orders are paid in more than one installment?

```yaml
view: payments_overview
measures: [order_payments.count_multi_installment]
```

### Q10 — Best sellers by revenue

```yaml
view: catalog_sales
measures: [order_items.total_price]
dimensions: [sellers.seller_id]
order:
  order_items.total_price: desc
limit: 10
```

> Note : l'agent doit avoir préalablement désambiguïsé "best" auprès de l'utilisateur. Si la question initiale est ambiguë, demander avant.

### Q16 — Late deliveries vs review score

C'est la question qui passe en standard **grâce à la dimension `delivery_status`** ajoutée au cube `orders` :

```yaml
view: reviews_overview
measures:
  - order_reviews.avg_score
  - order_reviews.count
dimensions: [orders.delivery_status]
```

Résultat attendu :

| delivery_status | avg_score | count |
|---|---|---|
| on_time | 4.3 | 85000 |
| late | 3.1 | 8000 |
| very_late | 2.2 | 2500 |
| not_delivered | — | 1500 |

L'agent peut compléter par une analyse : *"On-time deliveries score 4.3 vs 2.2 for very late — a clear correlation between delivery performance and satisfaction."*

---

## 10. Résolution des questions advanced via SQL API

Pour les 6 questions advanced, l'agent passe par `execute_sql` contre `olist_explorer`. Cette section détaille la résolution de Q12 (fil rouge, problème de grain) et donne le pattern pour les autres.

### Q12 — Avg review score by category (≥50 reviews, EN names)

**Stratégie côté agent**

1. **Reconnaissance des entités** : "review score", "product category", "50 reviews" → l'agent identifie les concepts via `describe_view('olist_explorer')`.
2. **Détection de la complexité** : "by category" + "review score" implique de croiser deux grains différents (order pour la review, item pour la catégorie). Une regular query échouerait avec fan-out.
3. **Choix du mode** : SQL API en pushdown avec CTE et window function.
4. **Génération du SQL** contre `olist_explorer`.

**SQL exécutable par l'agent**

```sql
WITH order_categories AS (
    SELECT
        order_id,
        category_name,
        SUM(item_total_price) AS total_price,
        COUNT(*) AS item_count
    FROM olist_explorer
    WHERE category_name IS NOT NULL
    GROUP BY order_id, category_name
),
ranked AS (
    SELECT
        order_id,
        category_name,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY item_count DESC, total_price DESC
        ) AS rn
    FROM order_categories
),
dominant_category_per_order AS (
    SELECT order_id, category_name
    FROM ranked
    WHERE rn = 1
)
SELECT
    d.category_name AS category,
    COUNT(*) AS review_count,
    ROUND(AVG(o.review_score), 2) AS avg_review_score
FROM olist_explorer o
JOIN dominant_category_per_order d ON o.order_id = d.order_id
WHERE o.review_score IS NOT NULL
GROUP BY d.category_name
HAVING COUNT(*) >= 50
ORDER BY avg_review_score DESC;
```

Cette requête est détectée comme **pushdown** par Cube. Tesseract génère le SQL équivalent vers PostgreSQL en respectant les joins déclarés dans `olist_explorer`.

**Points d'attention pour l'agent**

- L'agent doit **comprendre les approximations** : la "catégorie dominante" est une heuristique parmi d'autres (on pourrait pondérer par prix, ou répliquer la review autant de fois qu'il y a de catégories). C'est une décision métier.
- L'agent doit **communiquer cette heuristique** dans sa réponse à l'utilisateur, pour que le résultat soit interprétable.
- Pas de cache pré-agrégé sur ce type de requête — l'agent peut le signaler si la latence devient un problème.

### Q11 — Top 3 seller states (revenue/seller, 2017, states with >5 sellers)

```sql
WITH seller_state_metrics AS (
    SELECT
        seller_state,
        COUNT(DISTINCT seller_id) AS seller_count,
        SUM(item_total_price) AS total_revenue
    FROM olist_explorer
    WHERE EXTRACT(YEAR FROM purchased_at) = 2017
    GROUP BY seller_state
)
SELECT
    seller_state,
    seller_count,
    total_revenue,
    ROUND(total_revenue / seller_count, 2) AS revenue_per_seller
FROM seller_state_metrics
WHERE seller_count > 5
ORDER BY revenue_per_seller DESC
LIMIT 3;
```

### Q13 — Top 3 categories per customer state

```sql
WITH state_category_revenue AS (
    SELECT
        customers_state,
        category_name,
        SUM(item_total_price) AS revenue
    FROM olist_explorer
    WHERE category_name IS NOT NULL
      AND customers_state IS NOT NULL
    GROUP BY customers_state, category_name
),
ranked AS (
    SELECT
        customers_state,
        category_name,
        revenue,
        ROW_NUMBER() OVER (
            PARTITION BY customers_state
            ORDER BY revenue DESC
        ) AS rn
    FROM state_category_revenue
)
SELECT customers_state, category_name, revenue
FROM ranked
WHERE rn <= 3
ORDER BY customers_state, rn;
```

### Q14 — 2017 cohorts: 2nd purchase within 90 days

```sql
WITH customer_orders AS (
    SELECT DISTINCT
        customers_unique_id,
        order_id,
        purchased_at
    FROM olist_explorer
    WHERE customers_unique_id IS NOT NULL
),
first_orders_2017 AS (
    SELECT
        customers_unique_id,
        MIN(purchased_at) AS first_purchase_at
    FROM customer_orders
    GROUP BY customers_unique_id
    HAVING EXTRACT(YEAR FROM MIN(purchased_at)) = 2017
),
with_second AS (
    SELECT
        f.customers_unique_id,
        f.first_purchase_at,
        MIN(co.purchased_at) AS second_purchase_at
    FROM first_orders_2017 f
    LEFT JOIN customer_orders co
        ON f.customers_unique_id = co.customers_unique_id
        AND co.purchased_at > f.first_purchase_at
        AND co.purchased_at <= f.first_purchase_at + INTERVAL '90 days'
    GROUP BY f.customers_unique_id, f.first_purchase_at
)
SELECT
    DATE_TRUNC('month', first_purchase_at) AS cohort_month,
    COUNT(*) AS cohort_size,
    COUNT(second_purchase_at) AS converted,
    ROUND(100.0 * COUNT(second_purchase_at) / COUNT(*), 2) AS retention_pct
FROM with_second
GROUP BY 1
ORDER BY 1;
```

### Q15 — Worst delivery states (≥100 deliveries)

```sql
SELECT
    sellers_state AS seller_state,
    COUNT(DISTINCT order_id) AS delivery_count,
    ROUND(AVG(delay_days), 2) AS avg_delay_days
FROM olist_explorer
WHERE is_delivered = true
GROUP BY sellers_state
HAVING COUNT(DISTINCT order_id) >= 100
ORDER BY avg_delay_days DESC
LIMIT 10;
```

### Q17 — Revenue share: repeat vs one-time customers

```sql
WITH customer_order_count AS (
    SELECT
        customers_unique_id,
        COUNT(DISTINCT order_id) AS order_count
    FROM olist_explorer
    WHERE customers_unique_id IS NOT NULL
    GROUP BY customers_unique_id
),
customer_segment AS (
    SELECT
        customers_unique_id,
        CASE WHEN order_count >= 2 THEN 'repeat' ELSE 'one_time' END AS segment
    FROM customer_order_count
),
customer_revenue AS (
    SELECT
        e.customers_unique_id,
        SUM(e.item_total_price) AS total_revenue
    FROM olist_explorer e
    GROUP BY e.customers_unique_id
)
SELECT
    cs.segment,
    COUNT(*) AS customer_count,
    SUM(cr.total_revenue) AS revenue,
    ROUND(100.0 * SUM(cr.total_revenue) / SUM(SUM(cr.total_revenue)) OVER (), 2) AS revenue_share_pct
FROM customer_segment cs
JOIN customer_revenue cr ON cs.customers_unique_id = cr.customers_unique_id
GROUP BY cs.segment;
```

### Patterns récurrents en mode advanced

| Pattern | Quand l'utiliser | Exemple |
|---|---|---|
| `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` | Top-N par groupe, déduplication | Q13, Q12 (cat dominante) |
| `HAVING <agrégat> >= N` | Filtre minimal sur volume | Q11, Q12, Q15 |
| Self-join temporel | Cohort, comparaison historique | Q14 |
| `CASE WHEN ... THEN 'a' ELSE 'b'` + GROUP BY | Classification ad-hoc | Q17 |
| CTE multiples chaînées | Pipeline de transformation | Q12, Q14, Q17 |


---

## 11. Design des tools pour l'agent LangGraph

### Migration depuis l'existant

Tu as actuellement trois tools basés sur la REST API. Avec le passage des cubes en `public: false`, ces tools deviennent **sémantiquement incorrects** (ils manipulent des "views", pas des "cubes"). Plan de migration :

| Tool actuel | Tool cible | Changement |
|---|---|---|
| `list_cubes` | `list_views` | Renommage. Continue d'appeler `/v1/meta` mais filtre sur les objets `view`. Le résumé reste court (nom + description). |
| `get_cube_schema` | `describe_view` | Renommage + enrichissement : ajouter le flag `additive` sur les mesures, exposer `meta.example_questions` si présent, signaler les pièges (mesures non-additives, dimensions calculées). |
| `query_cube` | `query_view` | Renommage. Comportement inchangé (REST `/v1/load`). |

**Tools à ajouter** : `execute_sql` (mode advanced), `explain_sql` (validation préalable, choix de mode), et optionnellement `get_sample` / `get_distinct_values`.

### Schéma d'intégration cible

```
┌──────────────────────────────────────────────────────────────┐
│                      Agent LangGraph                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 1. Planning : analyse de la question                   │  │
│  │    - list_views, describe_view (introspection)         │  │
│  │    - décision : mode STANDARD ou ADVANCED ?            │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                   │
│              ┌───────────┴───────────┐                       │
│              ▼                       ▼                       │
│   ┌──────────────────────┐  ┌──────────────────────┐         │
│   │   Mode STANDARD      │  │   Mode ADVANCED      │         │
│   │   query_view         │  │   execute_sql        │         │
│   │   (REST /v1/load)    │  │   (SQL API, psycopg) │         │
│   │   sur view métier    │  │   sur olist_explorer │         │
│   └─────────┬────────────┘  └──────────┬───────────┘         │
└─────────────┼──────────────────────────┼─────────────────────┘
              │                          │
              ▼                          ▼
   ┌────────────────────┐    ┌──────────────────────┐
   │   Cube REST API    │    │    Cube SQL API      │
   │  /v1/meta /v1/load │    │  (port 15432, pg)    │
   │  cache + pré-agg   │    │  pushdown DataFusion │
   └─────────┬──────────┘    └──────────┬───────────┘
             │                          │
             └────────────┬─────────────┘
                          ▼
                   ┌──────────────┐
                   │  Cube Core   │
                   │  (semantic)  │
                   └──────┬───────┘
                          ▼
                   ┌──────────────┐
                   │  PostgreSQL  │
                   │   (Olist)    │
                   └──────────────┘
```

### Catalogue de tools recommandé

#### Tier 1 — Meta tools (introspection du modèle)

**`list_views`** — résumé léger, à charger systématiquement en début de session
```
signature: list_views() -> List[ViewSummary]
returns:   [{name, description, member_count, example_questions?: List[str]}]
api:       REST /v1/meta (filtré sur les views)
purpose:   première étape pour tout agent — comprendre ce qui est disponible
           sans charger les schémas complets dans le contexte
detail:    1 ligne par view ; idéal pour qu'un LLM choisisse une view sans
           saturer son contexte
```

**`describe_view`** — détail complet, à charger uniquement pour la view sélectionnée
```
signature: describe_view(view_name: str) -> ViewSchema
returns:   {
             name,
             description,
             example_questions: List[str],  # depuis meta.example_questions
             measures: [
               {name, type, description, format,
                additive: bool,            # False pour avg, count_distinct, ratios
                aggregation_warning?: str} # ex: "ne pas re-AVG côté agent"
             ],
             dimensions: [
               {name, type, description,
                is_calculated: bool}       # signale les dimensions calculées (CASE WHEN, etc.)
             ],
             segments: [{name, description}],
             hierarchies: [{name, levels}]
           }
api:       REST /v1/meta
purpose:   schéma complet pour qu'un LLM puisse construire des queries
           informées sur les pièges (non-additivité, dimensions calculées)
note:      ce niveau de détail n'est chargé que pour 1 à 2 views par requête,
           pas pour les 5 d'un coup
```

> **Note POC sur `example_questions`** : ce champ est optionnel. Tester d'abord sans pour évaluer les capacités du LLM à matcher question → view sur la base de la `description` seule. Si le routing échoue trop souvent, activer le champ et mesurer l'amélioration. Cube ne traite pas spécifiquement ce champ, il est juste exposé tel quel via `/v1/meta`.

#### Tier 2 — Standard tools (REST API, mode STANDARD)

**`query_view`** (remplace `query_cube`)
```
signature: query_view(
             view: str,
             measures: List[str] = [],
             dimensions: List[str] = [],
             filters: List[Filter] = [],
             time_dimensions: List[TimeDim] = [],
             segments: List[str] = [],
             order: Dict[str, str] = {},
             limit: int = 1000
           ) -> List[Dict]
api:       REST /v1/load
purpose:   requêtes structurées simples
benefit:   bénéficie du cache et des pré-agrégations
when:      l'agent peut exprimer la question avec ces primitives
```

#### Tier 3 — Advanced tools (SQL API, mode ADVANCED)

**`explain_sql`** — valider et inspecter un SQL sans l'exécuter
```
signature: explain_sql(sql: str) -> QueryPlan
returns:   {
             valid: bool,
             query_type: "regular" | "post_processing" | "pushdown",
             generated_sql: str,           # SQL vers la source upstream
             cubes_involved: [str],
             warnings: [str],
             errors: [str]
           }
api:       SQL API : EXPLAIN <sql>
purpose:   permet à l'agent de "regarder avant de sauter" — valide la syntaxe,
           anticipe si la requête sera regular/post-processing/pushdown,
           voit le SQL qui sera réellement exécuté côté upstream
when:      - avant un execute_sql lourd (validation préalable)
           - debug d'une requête qui échoue
           - vérifier que la requête tombe bien en pushdown comme attendu
```

**`execute_sql`** — exécuter un SQL contre le modèle sémantique
```
signature: execute_sql(
             sql: str,
             max_rows: int = 10000,
             timeout_s: int = 60
           ) -> {
             rows: List[Dict],
             columns: List[{name, type}],
             row_count: int,
             execution_time_ms: int
           }
api:       SQL API (port Postgres)
purpose:   exécution directe d'un SQL contre le modèle sémantique
when:      regular query insuffisante (CTE, window, multi-grain, fan-out…)
safety:    - validation : interdire DDL, DML, multi-statement
           - timeout strict
           - max_rows pour éviter les explosions mémoire
           - readonly user côté Postgres-Cube
```

#### Tier 4 — Optionnels (à considérer)

**`get_sample`**
```
signature: get_sample(view: str, n: int = 5) -> List[Dict]
purpose:   l'agent voit quelques lignes pour mieux raisonner sur la donnée
api:       SQL API : SELECT * FROM view LIMIT n
note:      utile pour qu'un LLM "ressente" la structure réelle
```

**`get_distinct_values`**
```
signature: get_distinct_values(view: str, dimension: str, limit: int = 50)
             -> List[Any]
purpose:   l'agent voit les valeurs réelles d'une dimension catégorielle
api:       REST /v1/load avec uniquement cette dimension
when:      avant un filtre, savoir si "shipped" / "Shipped" / "SHIPPED",
           ou voir la liste des states brésiliens disponibles
```

### Routing heuristique côté agent

L'agent peut décider du tool à appeler selon ces signaux dans la question utilisateur :

| Signal dans la question | Tool suggéré |
|---|---|
| Comptage, somme, moyenne sur une seule view | `query_view` (STANDARD) |
| "By X" où X est une dimension directe d'une view | `query_view` (STANDARD) |
| Comparaisons temporelles simples ("vs last month") | `query_view` (rolling_window) |
| Filtre sur agrégat (`HAVING COUNT > N`) | `execute_sql` (ADVANCED) |
| Ranking, top-N par groupe, déduplication | `execute_sql` (window functions) |
| Croisement de grains incompatibles | `execute_sql` (CTE) |
| Classification client/produit basée sur historique | `execute_sql` |
| Question floue, exploration | `list_views` + `describe_view` puis re-router |

Le système prompt de l'agent doit expliciter cette logique :

> *Tu disposes de deux familles de tools : `query_view` pour les agrégations simples (rapide, mis en cache), `execute_sql` pour les requêtes complexes nécessitant CTE, window functions ou agrégations multi-étapes. Avant d'utiliser `execute_sql`, vérifie qu'une `query_view` ne suffirait pas. Pour les requêtes SQL lourdes ou que tu hésites à exécuter, utilise `explain_sql` d'abord pour valider la syntaxe et vérifier qu'elles tombent en pushdown.*

### Garde-fous (POC → prod)

1. **Read-only côté SQL API** : `CUBEJS_SQL_USER` lié à un context où seul SELECT est exposé. Cube ne supporte de toute façon pas le DML via SQL API, mais double protection.
2. **Validation du SQL côté agent** : rejeter `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `;` multiple, `COPY`...
3. **Timeout strict** sur `execute_sql` (60s max au POC).
4. **Limite de lignes retournées** (`max_rows`) pour éviter les surcharges contexte LLM.
5. **Logging structuré** : pour chaque requête, logger `query_type`, durée, cubes touchés. Précieux pour repérer les patterns récurrents qui mériteraient d'être encapsulés en pré-agrégations ou en views métier.
6. **Quotas** : si l'agent est exposé en multi-utilisateur, mettre en place un rate-limiting côté agent (LangGraph supporte cela via state).

---

## 12. Limites et pièges à connaître

### Limites SQL

- **Sous-ensemble PostgreSQL** seulement — pas tous les opérateurs ni toutes les fonctions. Les fonctions exotiques peuvent ne pas être supportées.
- **Pas de DML** (INSERT/UPDATE/DELETE) ni DDL — la SQL API est purement lecture.
- **`COUNT(*)` ambigu** : remplacé par `MEASURE(count)` du cube concerné. Toujours préférer `MEASURE(count)` ou `COUNT(MEASURE(...))` explicite.

### Limites de performance

- Le **pushdown ne profite pas des pré-agrégations**. Une requête CTE complexe touche toujours les tables brutes — anticiper le coût.
- **Cache par hash** : la moindre différence de SQL (espace, alias) casse le cache.
- **Sessions concurrentes** : chaque connexion consomme de la mémoire. Pool de connexions côté agent indispensable en prod.

### Pièges modèle

- **Fan-out caché** : même avec primary keys, certains joins peuvent générer des fan-out invisibles si le modèle est mal défini. Toujours tester `COUNT(DISTINCT pk)` après ajout d'un join.
- **Mesures non-additives** : `avg`, `count_distinct`, ratios — interdire à l'agent de les pré-agréger.
- **`type: count` = `COUNT(DISTINCT primary_key)`** : si l'agent attend un `COUNT(*)`, il sera surpris. À documenter dans `describe_view`.

### Pièges côté agent

- **Hallucination de noms de mesures/dimensions** : toujours valider via `describe_view` avant de générer une requête. Le LLM invente sinon.
- **Confusion entre noms de cubes et tables sources** : avec `public: false`, l'agent ne doit jamais voir `orders` comme une table — uniquement les views (`olist_explorer`, `orders_overview`, etc.).
- **Sur-utilisation de `execute_sql`** : un agent paresseux pourrait toujours passer par SQL. Surveiller le ratio `query_view` / `execute_sql` ; un ratio trop faible signale soit un mauvais routing, soit un modèle insuffisamment riche.
- **Ambiguïté des mesures `customers.count` vs `customers.count_unique`** : l'agent doit lire les descriptions. Documenter explicitement dans le YAML.

---

## Annexe — Checklist de mise en route

### Côté Cube

- [ ] Tous les cubes ont `public: false`
- [ ] Toutes les primary keys sont déclarées
- [ ] Dimension `delivery_status` ajoutée au cube `orders`
- [ ] Dimension `delay_days` ajoutée au cube `orders`
- [ ] Les 4 views métier sont en place (`orders_overview`, `payments_overview`, `catalog_sales`, `reviews_overview`)
- [ ] La view exploratoire `olist_explorer` est en place
- [ ] `CUBEJS_PG_SQL_PORT` activé
- [ ] `CUBEJS_SQL_USER` / `CUBEJS_SQL_PASSWORD` configurés
- [ ] Test de connexion `psql` réussi
- [ ] Test SQL simple `SELECT MEASURE(count) FROM orders_overview` réussi
- [ ] Test SQL pushdown (la requête Q12 en §10) réussi

### Côté agent

- [ ] Migration `list_cubes` → `list_views`
- [ ] Migration `get_cube_schema` → `describe_view` (avec flag `additive`, `is_calculated`)
- [ ] Migration `query_cube` → `query_view`
- [ ] `execute_sql` opérationnel (SQL API)
- [ ] `explain_sql` opérationnel (validation préalable, choix de mode)
- [ ] Validation read-only du SQL avant exécution
- [ ] Timeout configuré
- [ ] Logs structurés en place (avec `query_type` pour suivi du routing)
- [ ] System prompt incluant la logique standard / advanced

### Évaluation du POC

- [ ] Les 17 questions du catalogue (§6) sont testées
- [ ] Mesure du ratio routing correct standard / advanced
- [ ] Test du champ `example_questions` activé vs désactivé (impact mesuré sur le routing)
- [ ] Latence moyenne par mode mesurée

### Évolution prod

- [ ] Passage JWT pour l'auth SQL API
- [ ] Access policies YAML sur les cubes sensibles
- [ ] Multi-tenant via `contextToAppId` si applicable
- [ ] Pré-agrégations sur les views métier critiques
- [ ] Monitoring des query types (regular / post-processing / pushdown)
- [ ] Cube intermédiaire `order_dominant_category` matérialisant la règle métier (fait passer Q12 en standard)
- [ ] Mesures de ratio matérialisées (ex: `share_multi_installment`)

---

*Document basé sur Cube Core v1.6.50 (mai 2026) et la documentation officielle cube.dev.*
