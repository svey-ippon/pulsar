# Bonnes pratiques — Modèle sémantique Cube (YAML)

> Document de référence basé sur la documentation officielle Cube, le style guide Cube, et les patterns observés en production.
> Version couverte : **Cube Core v1.6.50** (mai 2026)

---

## Table des matières

1. [Philosophie générale](#1-philosophie-générale)
2. [Structure de projet](#2-structure-de-projet)
3. [Conventions de nommage](#3-conventions-de-nommage)
4. [Cubes — règles fondamentales](#4-cubes--règles-fondamentales)
5. [Dimensions](#5-dimensions)
6. [Mesures](#6-mesures)
7. [Joins](#7-joins)
8. [Views (Vues)](#8-views-vues)
9. [Segments](#9-segments)
10. [Hierarchies](#10-hierarchies)
11. [Pré-agrégations](#11-pré-agrégations)
12. [Access Policies (v1.2+)](#12-access-policies-v12)
13. [Tesseract — moteur de nouvelle génération (v1.0+)](#13-tesseract--moteur-de-nouvelle-génération-v10)
14. [Calendar Cubes (v1.5+)](#14-calendar-cubes-v15)
15. [Pièges classiques](#15-pièges-classiques)
16. [Anti-patterns à éviter](#16-anti-patterns-à-éviter)
17. [Checklist avant mise en production](#17-checklist-avant-mise-en-production)

---

## 1. Philosophie générale

Cube est une **couche sémantique dataset-centric** : tout objet primaire (cube ou view) est conceptuellement une table. Son rôle est de centraliser la définition des métriques métier pour qu'elles soient interrogées de manière cohérente par tous les outils (BI, notebooks, API, agents IA).

Deux couches distinctes :

| Couche | Rôle | Visibilité |
|---|---|---|
| **Cubes** | Logique de données brute, joins, calculs | Privée (`public: false`) |
| **Views** | API publique exposée aux consommateurs | Publique (`public: true`, par défaut) |

> **Règle cardinale** : les cubes sont privés, les views sont publiques.

---

## 2. Structure de projet

```
cube_project/
└── model/
    ├── cubes/
    │   ├── finance/
    │   │   ├── stripe_invoices.yml
    │   │   └── stripe_payments.yml
    │   └── sales/
    │       └── opportunities.yml
    └── views/
        ├── finance/
        │   └── revenue.yml
        └── sales/
            └── pipeline.yml
```

- Séparer `model/cubes/` et `model/views/` — convention officielle depuis la v0.33, toujours en vigueur en v1.x.
- Créer des **sous-dossiers par domaine métier** (finance, sales, product…) pour refléter l'organisation de l'entreprise.
- Un cube = un fichier. Une view = un fichier.
- Nommer les fichiers en `snake_case`, au pluriel pour les cubes (`stripe_invoices.yml`).

---

## 3. Conventions de nommage

### YAML : snake_case partout

```yaml
# ✅ Correct
cubes:
  - name: stripe_invoices
    dimensions:
      - name: invoice_date
        sql: invoice_date
        type: time

# ❌ Incorrect (camelCase)
cubes:
  - name: stripeInvoices
    dimensions:
      - name: invoiceDate
```

Le YAML ne joue pas bien avec le camelCase (guillemets obligatoires, lisibilité dégradée). Le snake_case est la convention officielle depuis la v0.33 et reste la norme en v1.x.

### Noms de cubes

- Pluriel, représentant une entité métier : `orders`, `customers`, `stripe_invoices`.
- Pas de préfixe technique (pas de `tbl_`, pas de `fact_`, pas de `dim_`).
- Préfixe `base_` acceptable pour les cubes intermédiaires ou abstraits non exposés : `base_opportunities`.

### Noms de membres (dimensions/mesures)

- Noms clairs et compréhensibles par un non-technicien.
- Mesures : utiliser le nom de la métrique, pas le nom de la colonne (`total_revenue` plutôt que `amount_sum`).
- Dimensions de type `time` : suffixe `_at` (événement) ou `_date` (date seule) : `created_at`, `invoice_date`.

---

## 4. Cubes — règles fondamentales

### Déclaration minimale

```yaml
cubes:
  - name: orders
    sql_table: orders          # préférer sql_table quand c'est une table directe
    public: false              # toujours privé

    dimensions:
      - name: id
        sql: id
        type: number
        primary_key: true      # OBLIGATOIRE pour tout cube avec joins
```

### `sql_table` vs `sql`

```yaml
# ✅ Simple : table directe
cubes:
  - name: orders
    sql_table: public.orders

# ✅ Complexe : SQL personnalisé (CTE, sous-requête, filtre)
cubes:
  - name: recent_orders
    sql: >
      SELECT * FROM orders
      WHERE created_at > CURRENT_DATE - INTERVAL '90 days'
    public: false
```

Préférer `sql_table` quand aucune transformation n'est nécessaire — plus lisible, plus performant (Cube peut optimiser la génération SQL).

### Référencer les colonnes avec `{CUBE}`

Toujours préfixer les colonnes SQL avec `{CUBE}` (ou le nom du cube) pour éviter les ambiguïtés lors des joins :

```yaml
dimensions:
  - name: status
    sql: "{CUBE}.status"       # ✅ référence explicite
    type: string

measures:
  - name: completed_count
    sql: "{CUBE}.id"
    type: count
    filters:
      - sql: "{CUBE}.status = 'completed'"
```

---

## 5. Dimensions

### Types disponibles

| Type | Usage |
|---|---|
| `string` | Texte, catégories, statuts |
| `number` | Valeurs numériques, IDs techniques |
| `time` | Dates et timestamps (active le time-series dans les queries) |
| `boolean` | Drapeaux, flags |
| `geo` | Latitude/longitude (rare) |

### Primary key

```yaml
dimensions:
  - name: id
    sql: id
    type: number
    primary_key: true
```

- **Toujours définir une primary key** sur tout cube impliqué dans un join.
- `primary_key: true` rend automatiquement la dimension `public: false` — la remettre à `true` explicitement si on veut l'exposer.
- **Clé composite** : déclarer plusieurs dimensions avec `primary_key: true` ; Cube les concatène.

```yaml
# Clé composite
dimensions:
  - name: composite_key_a
    sql: tenant_id
    type: number
    primary_key: true
  - name: composite_key_b
    sql: order_id
    type: number
    primary_key: true
```

### Dimensions calculées

```yaml
dimensions:
  - name: full_name
    sql: "CONCAT({CUBE}.first_name, ' ', {CUBE}.last_name)"
    type: string

  - name: is_premium
    sql: "CASE WHEN {CUBE}.plan = 'premium' THEN true ELSE false END"
    type: boolean
```

### Sub-query dimensions

Permettent de ramener une **mesure d'un autre cube** comme dimension (pour filtrer ou grouper dessus) :

```yaml
# Dans le cube users
dimensions:
  - name: order_count
    sql: "{orders.count}"
    type: number
    sub_query: true
    public: false   # souvent interne, utilisé pour des calculs
```

> ⚠️ Les sub-query dimensions génèrent une sous-requête corrélée — attention aux performances sur de grands datasets.

### Dimensions `public: false`

Utiliser `public: false` pour les dimensions purement techniques (clés étrangères, colonnes intermédiaires) qui ne doivent pas apparaître dans les outils BI :

```yaml
dimensions:
  - name: user_id
    sql: user_id
    type: number
    public: false   # clé étrangère, pas utile à exposer
```

---

## 6. Mesures

### La règle `count` — comportement critique

> **`type: count` génère toujours `COUNT(DISTINCT primary_key)`, jamais `COUNT(*)`.**

C'est un comportement intentionnel de Cube pour éviter les doubles comptages lors des joins. Conséquences :

```yaml
# Ce que vous écrivez :
measures:
  - name: count
    type: count

# Ce que Cube génère (si primary_key = id) :
# SELECT COUNT(DISTINCT orders.id) FROM orders ...
```

- Si vous voulez un `COUNT(*)` brut → utiliser `type: count` sur un cube **sans join actif**, ou utiliser `type: sum` avec `sql: "1"`.
- Si la primary key n'est pas définie → Cube ne peut pas dédupliquer → erreur ou résultats incorrects.

### Types de mesures

```yaml
measures:
  # Comptage (DISTINCT sur la PK)
  - name: count
    type: count

  # Somme
  - name: total_revenue
    sql: amount
    type: sum

  # Moyenne
  - name: avg_order_value
    sql: amount
    type: avg

  # Min / Max
  - name: first_order_at
    sql: created_at
    type: min

  # Count distinct explicite (sur une colonne spécifique)
  - name: unique_customers
    sql: customer_id
    type: count_distinct

  # Count distinct approx (HyperLogLog - pour les très grands datasets)
  - name: approx_unique_users
    sql: user_id
    type: count_distinct_approx

  # Ratio (mesure calculée à partir d'autres mesures)
  - name: conversion_rate
    sql: "{paying_count} / NULLIF({count}, 0)"
    type: number
    format: percent
```

### Mesures filtrées (Filtered Aggregates)

```yaml
measures:
  - name: completed_orders
    sql: id
    type: count
    filters:
      - sql: "{CUBE}.status = 'completed'"

  - name: revenue_fr
    sql: amount
    type: sum
    filters:
      - sql: "{CUBE}.country = 'FR'"
```

### Rolling window (fenêtres temporelles glissantes)

```yaml
measures:
  # Cumul depuis le début du temps
  - name: cumulative_revenue
    sql: amount
    type: sum
    rolling_window:
      trailing: unbounded

  # Fenêtre glissante sur 30 jours
  - name: revenue_last_30d
    sql: amount
    type: sum
    rolling_window:
      trailing: 30 day

  # Year-to-date
  - name: revenue_ytd
    sql: amount
    type: sum
    rolling_window:
      type: to_date
      granularity: year
```

### Mesures basées sur d'autres mesures

```yaml
measures:
  - name: count
    type: count

  - name: paying_count
    sql: id
    type: count
    filters:
      - sql: "{CUBE}.is_paying = true"

  # ⚠️ Utiliser {} pour référencer une autre mesure, pas sql_table
  - name: paying_percentage
    sql: "1.0 * {paying_count} / NULLIF({count}, 0)"
    type: number
    format: percent
```

> **Important** : les mesures basées sur d'autres mesures ne sont **pas additives** — elles ne peuvent pas être pré-agrégées simplement. Voir la section Pré-agrégations.

### Formats d'affichage

```yaml
measures:
  - name: total_revenue
    sql: amount
    type: sum
    format: currency   # $1,234

  - name: conversion_rate
    sql: ...
    type: number
    format: percent    # 12.5%
```

---

## 7. Joins

### Direction des joins : une règle importante

**Les joins sont toujours définis dans le cube "source" (fact table), jamais dans la dimension table.**

Cube utilise toujours des `LEFT JOIN`. La direction (`many_to_one`, `one_to_many`, `one_to_one`) contrôle la **déduplication**. Cette terminologie a été standardisée en v0.33 et est la seule acceptée en v1.x.

```yaml
cubes:
  - name: orders           # fait
    sql_table: orders
    public: false

    joins:
      - name: customers    # dimension
        sql: "{CUBE}.customer_id = {customers.id}"
        relationship: many_to_one   # N orders → 1 customer

      - name: line_items   # sous-fait
        sql: "{CUBE}.id = {line_items.order_id}"
        relationship: one_to_many   # 1 order → N line_items
```

### Types de relations

| Relation | Exemple | Effet sur les mesures |
|---|---|---|
| `many_to_one` | orders → customers | Mesures de `orders` sont correctes |
| `one_to_many` | orders → line_items | Mesures de `orders` risquent le fan-out si mal gérées |
| `one_to_one` | users → user_profiles | Pas de multiplication |

### Fan-out : le danger principal

Un fan-out se produit quand un join `one_to_many` multiplie les lignes et gonfle les agrégats :

```yaml
# ⚠️ Situation dangereuse
# Si orders a un join one_to_many vers line_items,
# SUM(orders.amount) comptera le montant de l'order
# autant de fois qu'il y a de line_items !
```

**Solution** : Cube gère cela automatiquement via la primary key + `COUNT(DISTINCT)`. Assurez-vous que :
1. La primary key est définie sur chaque cube impliqué dans un join.
2. La relation est déclarée correctement.

### Joins multi-hop

Cube construit automatiquement les chemins de join entre cubes connectés. Mais si **deux chemins** existent pour rejoindre la même table → ambiguïté → utiliser les **Views** pour fixer le chemin explicitement.

```yaml
# Dans une view, on contrôle le chemin de join
views:
  - name: orders_with_country
    cubes:
      - join_path: orders           # chemin explicite
        includes: "*"
      - join_path: orders.customers # on passe par customers, pas directement
        includes:
          - country
```

### Joins sur clés composites

```yaml
joins:
  - name: campaigns
    sql: >
      {CUBE}.campaign_id = {campaigns.id}
      AND {CUBE}.customer_name = {campaigns.customer_name}
    relationship: many_to_one
```

---

## 8. Views (Vues)

### Rôle des views

Les views sont **l'API publique** de votre modèle sémantique. Elles :
- Exposent un sous-ensemble cohérent de mesures + dimensions aux outils BI.
- Contrôlent le chemin de join (résolution des ambiguïtés).
- Permettent de définir des **métriques** (vue à mesure unique).
- Assurent la **gouvernance** : on cache la complexité du graphe de cubes.

### Deux approches de design

**Entity-first** : la vue représente une entité dénormalisée (une "explore" à la Looker).

```yaml
views:
  - name: orders_explore
    description: "Tout ce qu'on peut savoir sur une commande"
    cubes:
      - join_path: orders
        includes: "*"
      - join_path: orders.customers
        includes:
          - name
          - country
          - segment
      - join_path: orders.line_items
        includes:
          - quantity
          - unit_price
```

**Metrics-first** : la vue représente une métrique unique avec ses dimensions de décomposition.

```yaml
views:
  - name: monthly_recurring_revenue
    description: "MRR mensuel, décomposable par plan et segment"
    cubes:
      - join_path: subscriptions
        includes:
          - mrr_amount          # la mesure clé
          - plan_name
          - created_at
      - join_path: subscriptions.customers
        includes:
          - segment
          - country
```

### Syntaxe complète d'une view

```yaml
views:
  - name: revenue_dashboard
    description: "Vue principale pour le dashboard revenus"
    # public: true par défaut

    cubes:
      - join_path: orders
        includes: "*"          # tout inclure
        excludes:
          - internal_flag      # sauf ça

      - join_path: orders.customers
        prefix: true           # préfixe les membres : customers_name, customers_country
        includes:
          - name
          - country

      - join_path: orders.customers
        alias: client          # préfixe custom : client_name, client_country
        includes:
          - segment
```

### `includes: "*"` avec `excludes`

```yaml
cubes:
  - join_path: orders
    includes: "*"
    excludes:
      - user_id         # clé étrangère technique
      - raw_payload     # données brutes non pertinentes
```

### Renommage dans les views

```yaml
cubes:
  - join_path: orders
    includes:
      - name: total_revenue
        alias: gross_revenue     # renommé pour le contexte de la vue
      - created_at
```

---

## 9. Segments

Les segments sont des **filtres pré-définis réutilisables**, stockés dans le modèle plutôt que dans les requêtes.

```yaml
cubes:
  - name: orders
    sql_table: orders
    public: false

    segments:
      - name: only_completed
        sql: "{CUBE}.status = 'completed'"

      - name: high_value
        sql: "{CUBE}.amount > 1000"

      - name: last_90_days
        sql: "{CUBE}.created_at > CURRENT_DATE - INTERVAL '90 days'"
```

- Utiliser les segments pour les filtres métier courants (simplification des queries API/BI).
- Les segments peuvent être inclus dans les views.
- Ne pas abuser : les filtres one-shot restent dans la query, pas dans le modèle.

---

## 10. Hierarchies (v1.2+)

Les hiérarchies permettent d'organiser des dimensions en niveaux de granularité pour le drill-down dans les outils BI (Power BI, Tableau, etc.).

```yaml
cubes:
  - name: orders
    sql_table: orders
    public: false

    dimensions:
      - name: created_at
        sql: created_at
        type: time
      - name: status
        sql: status
        type: string
      - name: country
        sql: country
        type: string
      - name: region
        sql: region
        type: string
      - name: city
        sql: city
        type: string

    hierarchies:
      - name: geo
        title: "Geographic Hierarchy"
        levels:
          - country
          - region
          - city

      - name: date_hierarchy
        title: "Date"
        levels:
          - created_at.year
          - created_at.quarter
          - created_at.month
          - created_at.week
          - created_at.day
```

- Les hiérarchies sont déclarées dans les cubes mais **exposées via les views**.
- Particulièrement utiles pour les intégrations DAX (Power BI) et Tableau.
- Une hiérarchie `levels` liste les dimensions du grain le plus large au plus fin.

---

## 11. Pré-agrégations

### Principes

Les pré-agrégations matérialisent des résultats SQL pour accélérer les requêtes. Elles sont définies **dans les cubes**, et réutilisées par les views.

```yaml
cubes:
  - name: orders
    sql_table: orders
    public: false

    pre_aggregations:
      - name: orders_by_day
        measures:
          - count
          - total_revenue
        dimensions:
          - status
        time_dimension: created_at
        granularity: day
        refresh_key:
          every: 1 hour
```

### Mesures additives vs non-additives

| Additive (rollup possible) | Non-additive |
|---|---|
| `count`, `sum`, `min`, `max` | `avg`, `count_distinct`, ratios |
| `count_distinct_approx` | Mesures basées sur d'autres mesures |

Pour les mesures non-additives, la pré-agrégation doit inclure **toutes les dimensions** nécessaires au recalcul :

```yaml
# avg ne peut pas être rollupé : stocker sum + count séparément
pre_aggregations:
  - name: for_avg
    measures:
      - total_amount    # sum
      - count           # count
    dimensions:
      - status
    time_dimension: created_at
    granularity: day
```

### Types de pré-agrégations

```yaml
pre_aggregations:
  # Rollup standard (le plus courant)
  - name: main_rollup
    type: rollup            # par défaut, implicite
    measures: [count, total_revenue]
    dimensions: [status]
    time_dimension: created_at
    granularity: day

  # SQL original matérialisé (snapshot du résultat de la requête SQL du cube)
  - name: raw_cache
    type: original_sql
    # Pas de measures/dimensions — matérialise le sql du cube

  # Rollup join (pour joindre des pré-agrégations de cubes différents)
  - name: orders_with_customers
    type: rollup_join
    measures: [orders.count]
    dimensions: [customers.name]
    rollups:
      - orders.main_rollup
      - customers.customers_rollup
```

### Partitionnement incrémental

```yaml
pre_aggregations:
  - name: orders_incremental
    measures: [count, total_revenue]
    time_dimension: created_at
    granularity: day
    partition_granularity: month    # partitionné par mois
    refresh_key:
      every: 1 hour
      incremental: true
      update_window: 3 day          # recalcule les 3 derniers jours
```

---

## 12. Access Policies (v1.2+)

Les access policies permettent de définir du **contrôle d'accès déclaratif** directement dans le modèle YAML — row-level security et member-level security — sans passer par le `queryRewrite` en JavaScript.

### Row-level security

```yaml
cubes:
  - name: orders
    sql_table: orders
    public: false

    access_policy:
      - role: analyst
        row_level:
          filters:
            - member: "{CUBE}.country"
              operator: equals
              values_v2:
                context: COMPILE_CONTEXT.securityContext.country

      - role: admin
        # Pas de filtre → accès total pour les admins
```

### Member-level security (masquage de colonnes)

```yaml
cubes:
  - name: customers
    sql_table: customers
    public: false

    access_policy:
      - role: "*"                  # s'applique à tous les rôles
        member_level:
          excludes:
            - email                # masque la colonne email
            - phone_number

      - role: data_owner
        member_level:
          includes: "*"            # accès complet pour data_owner
```

### Règles d'usage

- Les rôles sont définis dans le **security context** JWT (`{ role: "analyst" }`).
- `"*"` comme rôle = règle par défaut applicable à tous.
- Les policies se cumulent : un utilisateur avec plusieurs rôles obtient l'union des accès.
- Les access policies s'appliquent aussi aux views (héritage depuis les cubes sous-jacents).
- Disponible dans Cube Core à partir de **v1.2.0**.

---

## 13. Tesseract — moteur de nouvelle génération (v1.0+)

Tesseract est le nouveau moteur SQL de Cube (en Rust, basé sur DataFusion), introduit en preview avec v1.0.0 (octobre 2024) et progressivement généralisé. Il remplace le moteur JavaScript historique.

### Activer Tesseract

```bash
# Variable d'environnement pour activer le SQL planner Tesseract
CUBEJS_TESSERACT_SQL_PLANNER=true
```

À partir de **v1.6.50**, l'orchestrateur natif est activé pour tous les cas et ne peut plus être désactivé.

### Ce que Tesseract apporte au YAML

**1. Multi-stage calculations** — calculs en plusieurs passes (agrégation sur agrégation) sans sous-requêtes manuelles :

```yaml
measures:
  # Calcul classique
  - name: total_revenue
    sql: amount
    type: sum

  # Pourcentage du total — multi-stage, impossible sans Tesseract
  - name: revenue_share
    type: number
    sql: "{total_revenue} / SUM({total_revenue}) OVER ()"
    # Avec Tesseract, Cube génère correctement la fenêtre
```

**2. Rolling window sans date range obligatoire** — avant Tesseract, un `rolling_window` exigeait un filtre de date dans la query. Plus nécessaire avec Tesseract :

```yaml
measures:
  - name: cumulative_revenue
    sql: amount
    type: sum
    rolling_window:
      trailing: unbounded     # fonctionne sans date range avec Tesseract
```

**3. Period-over-period natif** — calculs year-over-year, month-over-month directement dans le modèle :

```yaml
measures:
  - name: revenue_yoy
    sql: amount
    type: sum
    time_shift:
      - time_dimension: created_at
        interval: 1 year
        type: prior
```

### Compatibilité

Tesseract supporte toutes les sources de données majeures depuis v1.5. Les modèles YAML existants sont **compatibles sans modification** — Tesseract est un changement de moteur SQL, pas de syntaxe.

---

## 14. Calendar Cubes (v1.5+)

Les calendar cubes permettent de définir des calendriers métier personnalisés (fiscal, broadcasting, etc.) pour remplacer le calendrier grégorien standard dans les calculs temporels.

```yaml
cubes:
  - name: fiscal_calendar
    sql: >
      SELECT
        date_day,
        fiscal_year,
        fiscal_quarter,
        fiscal_month,
        fiscal_week
      FROM dim_fiscal_calendar
    calendar: true             # ← marque ce cube comme calendar cube
    public: false

    dimensions:
      - name: date_day
        sql: date_day
        type: time
        primary_key: true

      - name: fiscal_year
        sql: fiscal_year
        type: number

      - name: fiscal_quarter
        sql: fiscal_quarter
        type: number
```

Utilisation dans un autre cube :

```yaml
cubes:
  - name: orders
    sql_table: orders
    public: false

    dimensions:
      - name: created_at
        sql: created_at
        type: time
        # Référencer le calendar cube pour les granularités fiscales
        granularities:
          - name: fiscal_year
            interval: 1 year
            calendar: fiscal_calendar
```

---

## 15. Pièges classiques

### 1. Oublier la `primary_key`

```yaml
# ❌ Pas de primary_key → Cube ne peut pas dédupliquer
cubes:
  - name: orders
    sql_table: orders
    joins:
      - name: customers
        ...

# ✅ Toujours définir la primary_key sur les cubes avec joins
cubes:
  - name: orders
    sql_table: orders
    dimensions:
      - name: id
        sql: id
        type: number
        primary_key: true
```

### 2. Mal comprendre `type: count`

```yaml
# Ce que CUBE génère pour type: count avec primary_key = id :
# COUNT(DISTINCT orders.id)

# Si vous voulez compter les lignes d'une table de log sans PK unique :
measures:
  - name: event_count
    sql: "1"
    type: sum          # SUM(1) = COUNT(*) sans déduplication
```

### 3. Exposer des cubes directement (sans views)

Les cubes exposés (`public: true`) permettent aux outils BI d'effectuer des joins arbitraires → risque de fan-out, de chemins de join ambigus, de métriques incohérentes. Toujours passer par des views.

### 4. Chemins de join ambigus

Si `orders` peut rejoindre `countries` directement ET via `customers`, Cube lève une erreur. Résolution :

```yaml
# Fixer le chemin dans la view
views:
  - name: orders_view
    cubes:
      - join_path: orders.customers.countries   # chemin explicite
        includes: [country_name]
```

### 5. Mesures `avg` dans les pré-agrégations

`AVG` n'est pas additive : `AVG(AVG(a), AVG(b)) ≠ AVG(a, b)`. Ne jamais mettre directement une mesure `avg` dans une pré-agrégation sans stocker `sum` + `count` séparément.

### 6. `sub_query: true` sur des tables volumineuses

Les sub-query dimensions génèrent une sous-requête corrélée pour chaque ligne. Sur des millions de lignes, c'est catastrophique en performance. Alternatives : matérialiser en dbt, utiliser un join explicite.

### 7. Référencer des colonnes sans `{CUBE}`

```yaml
# ❌ Ambigu lors des joins
measures:
  - name: total
    sql: amount
    type: sum

# ✅ Toujours préfixer
measures:
  - name: total
    sql: "{CUBE}.amount"
    type: sum
```

---

## 16. Anti-patterns à éviter

| Anti-pattern | Pourquoi c'est problématique | Alternative |
|---|---|---|
| Cubes `public: true` exposés directement | Joins arbitraires, métriques incohérentes | Views pour tout exposer |
| Logique métier dans le `sql` d'un cube | Duplication, maintenabilité | Mesures calculées, dbt models |
| Un cube couvrant plusieurs tables non liées | Périmètre flou, performance | Un cube = une entité |
| Pré-agrégations sans `time_dimension` | Toute la table, jamais incrémental | Ajouter un `time_dimension` |
| Mesures de ratio dans les pré-agrégations | Non-additivité → résultats faux | Stocker numérateur + dénominateur |
| Joins définis des deux côtés (bidirectionnel) | Graphe de join cyclique → erreur | Join unidirectionnel depuis la fact table |
| Noms trop techniques (`amt`, `cnt`, `flg`) | Illisible pour les non-techniciens | Noms métier complets |

---

## 17. Checklist avant mise en production

### Structure

- [ ] Dossiers `model/cubes/` et `model/views/` créés et respectés
- [ ] Sous-dossiers par domaine métier
- [ ] Un fichier = un cube ou une view

### Cubes

- [ ] Tous les cubes ont `public: false`
- [ ] Tous les cubes impliqués dans des joins ont une `primary_key`
- [ ] Les colonnes SQL référencent toujours `{CUBE}.colonne`
- [ ] `sql_table` utilisé quand pas de transformation nécessaire

### Dimensions

- [ ] Les clés étrangères sont `public: false`
- [ ] Les `primary_key` sont `public: false` (sauf si besoin explicite)
- [ ] Les dimensions `time` portent `_at` ou `_date`

### Mesures

- [ ] Le comportement de `type: count` (DISTINCT) est bien compris et voulu
- [ ] Les mesures de ratio utilisent `NULLIF(denominateur, 0)` pour éviter la division par zéro
- [ ] Les mesures non-additives (`avg`, `count_distinct`) sont documentées

### Joins

- [ ] Joins définis uniquement dans les cubes "source"
- [ ] Relations correctement typées (`many_to_one`, `one_to_many`, `one_to_one`)
- [ ] Chemins de join ambigus résolus dans les views

### Views

- [ ] Chaque view a une `description` claire
- [ ] Les clés étrangères et colonnes techniques sont exclues (`excludes`)
- [ ] Le chemin de join est explicite si potentiellement ambigu

### Pré-agrégations

- [ ] Granularité adaptée aux usages (day pour dashboards, week/month pour reports)
- [ ] `refresh_key` configuré
- [ ] Mesures non-additives gérées (sum + count au lieu de avg)
- [ ] Partitionnement incrémental pour les tables volumineuses

---

## Référence rapide — Types de mesures

```yaml
measures:
  - name: count           ; type: count            → COUNT(DISTINCT pk)
  - name: total           ; type: sum               → SUM(col)
  - name: average         ; type: avg               → AVG(col)
  - name: minimum         ; type: min               → MIN(col)
  - name: maximum         ; type: max               → MAX(col)
  - name: uniq            ; type: count_distinct    → COUNT(DISTINCT col)
  - name: approx_uniq     ; type: count_distinct_approx → HyperLogLog
  - name: ratio           ; type: number            → expression libre
```

## Référence rapide — Types de dimensions

```yaml
dimensions:
  - name: label     ; type: string
  - name: amount    ; type: number
  - name: ts        ; type: time
  - name: active    ; type: boolean
```

---
