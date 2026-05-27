# Plan d'implémentation — Mode Standard v2

> Périmètre : **mode standard uniquement** (REST API Cube sur views métier).  
> Le mode advanced (SQL API, `olist_explorer`) est hors scope.  
> Source de référence : [PLAN_V2.md](./PLAN_V2.md) §1–11.

---

## Vue d'ensemble

L'objectif est de passer de l'architecture actuelle (9 cubes publics, 3 tools LangChain sur les cubes) à une architecture gouvernée (cubes privés + views métier) avec des tools alignés sur les views.

```
AVANT                              APRÈS
──────────────────────────         ──────────────────────────────────
Agent                              Agent
  list_cubes    ──────────►          list_views    ──────────────►
  get_cube_schema ─────────►          describe_view  ────────────►  Views (publiques)
  query_cube    ──────────►          query_view    ──────────────►    orders_overview
                                                                      payments_overview
  Cubes (publics)                    Cubes (public: false)            catalog_sales
    orders                             orders                         reviews_overview
    order_items                        order_items
    order_reviews                      order_reviews          ◄──────── Cubes enrichis
    order_payments                     order_payments
    customers                          customers
    sellers                            sellers
    products                           products
    product_category_name_translation  product_category_name_translation
    geolocation                        geolocation
```

---

## État des lieux (point de départ)

### Ce qui existe

| Fichier | État actuel | Delta v2 |
|---|---|---|
| `cube/model/cubes/orders.yml` | public, pas de `delivery_status`, pas de `delay_days` | Ajouter `public: false` + 3 dimensions calculées + 2 mesures |
| `cube/model/cubes/order_payments.yml` | public, pas de `is_multi_installment`, pas de `count_multi_installment` | Ajouter `public: false` + 1 dimension + 2 mesures |
| `cube/model/cubes/order_items.yml` | public, `total_revenue` + `freight_value` | Ajouter `public: false` seulement |
| `cube/model/cubes/order_reviews.yml` | public, `avg_review_score` + `review_count` | Ajouter `public: false` seulement |
| `cube/model/cubes/customers.yml` | public, `unique_customer_count` | Ajouter `public: false` seulement |
| `cube/model/cubes/sellers.yml` | public | Ajouter `public: false` seulement |
| `cube/model/cubes/products.yml` | public | Ajouter `public: false` seulement |
| `cube/model/cubes/product_category_name_translation.yml` | public | Ajouter `public: false` seulement |
| `cube/model/cubes/geolocation.yml` | public | Ajouter `public: false` (hors scope des views pour l'instant) |
| `cube/model/views/example_view.yml` | Commenté, placeholder | Remplacer par les 4 views métier |
| `pulsar-agent/src/pulsar_agent/tools.py` | `list_cubes`, `get_cube_schema`, `query_cube` | Renommage complet + enrichissement |
| `pulsar-agent/src/pulsar_agent/cube_client.py` | Protocol + CubeClient | Nouveaux membres |
| `pulsar-agent/src/pulsar_agent/prompt.py` | Référence aux cubes | Mise à jour vers views |
| `tests/test_cube_model.py` | Tests cubes uniquement | + Tests views |
| `pulsar-agent/tests/test_agent_tools.py` | 3 tools, noms actuels | Refonte complète |
| `CLAUDE.md` | Architecture cubes | Mise à jour |

### Alignement noms membres (cube actuel → view PLAN_V2)

> Les views exposent les membres des cubes sous leur **nom de cube réel**. Le tableau ci-dessous réconcilie les noms du PLAN_V2 (axé PostgreSQL) avec nos noms Snowflake réels.

| PLAN_V2 (nom view) | Cube source | Membre cube réel | Remarque |
|---|---|---|---|
| `total_price` | `order_items` | `total_revenue` | Dans les views, on expose `total_revenue` |
| `total_freight` | `order_items` | `freight_value` | Dans les views, on expose `freight_value` |
| `avg_score` | `order_reviews` | `avg_review_score` | |
| `count` (reviews) | `order_reviews` | `review_count` | |
| `score` (dim) | `order_reviews` | `review_score` | |
| `count_unique` | `customers` | `unique_customer_count` | |
| `total_value` | `order_payments` | `payment_value` | |
| `purchased_at` | `orders` | `order_purchase_timestamp` | |
| `delivered_at` | `orders` | `order_delivered_customer_date` | |
| `status` | `orders` | `order_status` | |
| `category_name` | `product_category_name_translation` | `product_category_name_english` | |
| `seller_id` | `sellers` | `seller_id` | identique |
| `state` (customer) | `customers` | `customer_state` | |
| `state` (seller) | `sellers` | `seller_state` | |

---

## Phase 1 — Enrichissement des cubes Cube

### Étape 1.1 — Passage en `public: false` (tous les cubes)

**Impact** : une fois `public: false` posé, les cubes disparaissent de `/v1/meta` et de la SQL API. Seules les views resteront visibles. Cette étape doit être réalisée **en même temps que** la création des views (pas avant).

**Fichiers** : tous les `*.yml` dans `cube/model/cubes/`.

**Changement** : ajouter `public: false` au niveau racine du cube.

```yaml
cubes:
  - name: orders
    public: false   # ← ajouter
    ...
```

---

### Étape 1.2 — Enrichir `orders.yml`

Trois dimensions calculées + deux mesures à ajouter.

#### Dimensions à ajouter

```yaml
      # ── Dimensions calculées ──────────────────────────────────────────────
      # Transforment des questions ADVANCED en STANDARD en encapsulant
      # la logique métier directement dans le cube.

      - name: delay_days
        sql: >
          DATEDIFF('day',
            {CUBE}."ORDER_ESTIMATED_DELIVERY_DATE",
            {CUBE}."ORDER_DELIVERED_CUSTOMER_DATE"
          )
        type: number
        description: >
          Nombre de jours de retard à la livraison (positif = en retard,
          négatif = en avance). NULL si la commande n'est pas encore livrée.

      - name: delivery_status
        sql: >
          CASE
            WHEN {CUBE}."ORDER_DELIVERED_CUSTOMER_DATE" IS NULL THEN 'not_delivered'
            WHEN {CUBE}."ORDER_DELIVERED_CUSTOMER_DATE"
                 <= {CUBE}."ORDER_ESTIMATED_DELIVERY_DATE" THEN 'on_time'
            WHEN {CUBE}."ORDER_DELIVERED_CUSTOMER_DATE"
                 <= DATEADD('day', 7, {CUBE}."ORDER_ESTIMATED_DELIVERY_DATE") THEN 'late'
            ELSE 'very_late'
          END
        type: string
        description: >
          Statut de livraison calculé : 'on_time' (livré à temps ou en avance),
          'late' (jusqu'à 7j de retard), 'very_late' (plus de 7j), 
          'not_delivered' (pas encore livré). Utiliser pour Q16 (satisfaction vs livraison).

      - name: is_delivered
        sql: "({CUBE}.\"ORDER_DELIVERED_CUSTOMER_DATE\" IS NOT NULL)"
        type: boolean
        description: "True si la commande a été livrée au client."
```

> ⚠️ **Syntaxe Snowflake** : `DATEDIFF` et `DATEADD` sont les fonctions Snowflake. PostgreSQL utilise `DATE_PART` / `INTERVAL`. À tester contre Cube/Snowflake.

#### Mesures à ajouter

```yaml
      - name: avg_delay_days
        sql: "{CUBE}.delay_days"
        type: avg
        description: >
          Délai moyen de livraison en jours (positif = retard moyen).
          ⚠️ Non-additive — ne pas sommer entre états ou catégories.

      - name: delivered_count
        sql: "{CUBE}.\"ORDER_ID\""
        type: count
        filters:
          - sql: "{CUBE}.\"ORDER_DELIVERED_CUSTOMER_DATE\" IS NOT NULL"
        description: "Nombre de commandes effectivement livrées."
```

---

### Étape 1.3 — Enrichir `order_payments.yml`

#### Dimension à ajouter

```yaml
      - name: is_multi_installment
        sql: "({CUBE}.\"PAYMENT_INSTALLMENTS\" > 1)"
        type: boolean
        description: "True si le paiement est en plusieurs fois (> 1 échéance)."
```

#### Mesures à ajouter

```yaml
      - name: count_multi_installment
        sql: "{CUBE}.\"ORDER_ID\""
        type: count
        filters:
          - sql: "{CUBE}.\"PAYMENT_INSTALLMENTS\" > 1"
        description: "Nombre de paiements effectués en plusieurs mensualités."

      - name: avg_installments
        sql: "{CUBE}.\"PAYMENT_INSTALLMENTS\""
        type: avg
        description: >
          Nombre moyen d'échéances par paiement.
          ⚠️ Non-additive — ne pas sommer.
```

---

### Étape 1.4 — Ajouter les joins bidirectionnels dans `orders.yml`

#### Contexte : le graphe de joins Cube est directionnel

Le graphe de joins de Cube est **directionnel**. Un join déclaré `order_reviews → orders` (many_to_one) ne permet **pas** la navigation inverse `orders → order_reviews`.

Or, plusieurs views doivent partir de `orders` pour atteindre les faits satellites :

| View | Join path problématique | Sens requis |
|---|---|---|
| `orders_overview` | `orders.order_reviews` | orders → order_reviews |
| `orders_overview` | `orders.customers` | orders → customers ✅ (déjà déclaré) |

**Décision** : ajouter trois joins `one_to_many` dans `orders.yml`, en supplément du join `customers` existant.

#### Pourquoi c'est sûr dans notre cas

La doc Cube déconseille les joins bidirectionnels par défaut car ils peuvent créer des "diamond subgraphs" (plusieurs chemins entre deux cubes → Cube choisit un chemin imprévu). Trois éléments rendent notre cas sûr :

1. **Schéma en étoile centré sur `orders`** — pas de cycle métier réel ; les faits satellites (`order_items`, `order_reviews`, `order_payments`) ne se joignent pas entre eux.
2. **Toutes les views fixent `join_path` explicitement** — Cube est forcé de suivre le chemin déclaré, sans court-circuit possible.
3. **Joins inverses confinés à `orders`** — jamais entre faits satellites, ce qui évite la création de cycles.

#### Joins à ajouter dans `orders.yml`

```yaml
    joins:
      - name: customers               # ← déjà présent
        sql: "{CUBE.customer_id} = {customers.customer_id}"
        relationship: many_to_one

      # ─── Joins inverses (bidirectionnels) ─────────────────────────────
      - name: order_items
        sql: "{CUBE}.\"ORDER_ID\" = {order_items.order_id}"
        relationship: one_to_many

      - name: order_reviews
        sql: "{CUBE}.\"ORDER_ID\" = {order_reviews.order_id}"
        relationship: one_to_many

      - name: order_payments
        sql: "{CUBE}.\"ORDER_ID\" = {order_payments.order_id}"
        relationship: one_to_many
```

> Les déclarations existantes dans `order_items.yml`, `order_reviews.yml`, `order_payments.yml` (many_to_one → orders) sont **conservées telles quelles**.

#### Garde-fou : test d'intégrité (anti-fan-out)

Après déploiement, vérifier que `orders.count` est stable quelle que soit la dimension ajoutée :

```sql
-- Ces deux requêtes doivent retourner la même valeur
SELECT MEASURE(count) FROM orders_overview;
SELECT MEASURE(count) FROM orders_overview GROUP BY delivery_status;
```

Si les valeurs diffèrent → fan-out non géré → primary key manquante ou mal déclarée.

Ce test d'intégrité est repris en **test statique** dans la Phase 4 (test sur le modèle) et doit être vérifié **manuellement live** après déploiement.

---

## Phase 2 — Création des views métier

Structure des fichiers (plat, cohérent avec l'existant) :

```
cube/model/views/
├── example_view.yml            ← Remplacer par les 4 views (supprimer ou vider)
├── orders_overview.yml         ← Nouveau
├── payments_overview.yml       ← Nouveau
├── catalog_sales.yml           ← Nouveau
└── reviews_overview.yml        ← Nouveau
```

### Note sur les join_path des views

Les joins bidirectionnels dans `orders.yml` (Étape 1.4) rendent possibles les `join_path` suivants dans les views :

- `orders.customers` ✅ (join many_to_one déjà déclaré dans orders)
- `orders.order_reviews` ✅ (join one_to_many ajouté en 1.4)
- `orders.order_items` ✅ (join one_to_many ajouté en 1.4)
- `orders.order_payments` ✅ (join one_to_many ajouté en 1.4)
- `order_reviews.orders` ✅ (join many_to_one déclaré dans order_reviews)
- `order_reviews.orders.customers` ✅ (chaîne via joins existants)
- `order_items.orders` ✅ (join many_to_one déclaré dans order_items)
- `order_items.products.product_category_name_translation` ✅ (via join déclaré dans products)
- `order_items.sellers` ✅ (join many_to_one déclaré dans order_items)
- `order_payments.orders` ✅ (join many_to_one déclaré dans order_payments)

---

### Étape 2.1 — `orders_overview.yml`

Questions couvertes : Q1 (count total), Q2 (count par état), Q7 (revenu mensuel), Q16 (livraison vs satisfaction).

```yaml
views:
  - name: orders_overview
    description: >
      Vue centrée sur les commandes : volume, statut, performance de livraison
      et satisfaction. Grain : order_id.
      Couvre les questions sur le nombre de commandes, la livraison, et la
      corrélation livraison/satisfaction.
    meta:
      summary: "Commandes : volume, statut, livraison, satisfaction. Grain order_id."

    cubes:
      - join_path: orders
        includes:
          - order_id
          - order_status
          - order_purchase_timestamp
          - order_delivered_customer_date
          - delivery_status
          - delay_days
          - is_delivered
          - count
          - delivered_count
          - avg_delay_days

      - join_path: orders.customers
        includes:
          - customer_state
          - customer_city
          - unique_customer_count

      - join_path: orders.order_reviews    # ← vérifier la traversée inverse
        includes:
          - review_score
          - avg_review_score
          - review_count
```

---

### Étape 2.2 — `payments_overview.yml`

Questions couvertes : Q3 (méthodes de paiement), Q5 (valeur totale), Q8 (part multi-installments), Q9 (count multi-installments).

```yaml
views:
  - name: payments_overview
    description: >
      Vue centrée sur les paiements : montants, méthodes, échéances.
      Grain : (order_id, payment_sequential).
      Couvre les questions sur les méthodes de paiement, la valeur encaissée,
      et la part de paiements en plusieurs fois.
    meta:
      summary: "Paiements : montants, méthodes, échéances. Grain (order_id, payment_sequential)."

    cubes:
      - join_path: order_payments
        includes:
          - payment_type
          - payment_installments
          - is_multi_installment
          - count
          - payment_value
          - count_multi_installment
          - avg_installments

      - join_path: order_payments.orders
        includes:
          - order_purchase_timestamp
          - order_status
```

---

### Étape 2.3 — `catalog_sales.yml`

Questions couvertes : Q5 (variante GMV), Q6 (top catégories), Q7 (revenu mensuel), Q10 (meilleurs vendeurs).

```yaml
views:
  - name: catalog_sales
    description: >
      Vue centrée sur les ventes au grain item : revenus, catégories, vendeurs.
      Grain : (order_id, order_item_id).
      Couvre les questions sur le top des catégories, les meilleurs vendeurs,
      et le revenu par produit. Note : total_revenue exclut le fret.
    meta:
      summary: "Ventes par item : revenus, catégories EN, vendeurs. Grain (order_id, order_item_id)."

    cubes:
      - join_path: order_items
        includes:
          - count
          - total_revenue
          - freight_value

      - join_path: order_items.orders
        includes:
          - order_purchase_timestamp
          - order_status

      - join_path: order_items.products
        includes:
          - product_id

      - join_path: order_items.products.product_category_name_translation
        includes:
          - product_category_name_english

      - join_path: order_items.sellers
        prefix: true
        includes:
          - seller_id
          - seller_state
          - seller_city
```

---

### Étape 2.4 — `reviews_overview.yml`

Questions couvertes : Q4 (avg score global), Q16 (satisfaction vs livraison).

```yaml
views:
  - name: reviews_overview
    description: >
      Vue centrée sur les avis clients. Grain : order_id (une review par order).
      Couvre les questions sur le score moyen global et la corrélation avec
      la performance de livraison.
      ⚠️ Ne contient PAS la catégorie produit — problème de grain (utiliser
      le mode advanced pour cela).
    meta:
      summary: "Avis clients : score moyen, corrélation livraison. Grain order_id."

    cubes:
      - join_path: order_reviews
        includes:
          - review_score
          - review_creation_date
          - review_count
          - avg_review_score

      - join_path: order_reviews.orders
        includes:
          - order_status
          - order_purchase_timestamp
          - delivery_status
          - delay_days

      - join_path: order_reviews.orders.customers
        includes:
          - customer_state
          - customer_city
```

---

### Couverture des 17 questions (mode standard)

| View | Questions | Grain |
|---|---|---|
| `orders_overview` | Q1, Q2, Q7 (variante), Q16 | `order_id` |
| `payments_overview` | Q3, Q5 (encaissé), Q8, Q9 | `(order_id, payment_sequential)` |
| `catalog_sales` | Q5 (GMV), Q6, Q7 (variante), Q10 | `(order_id, order_item_id)` |
| `reviews_overview` | Q4, Q16 | `order_id` |
| *(advanced — hors scope)* | Q11, Q12, Q13, Q14, Q15, Q17 | — |

---

## Phase 3 — Migration des tools Python

### Décision : rupture propre

Pas de backward compatibility. Les 3 anciens tools sont remplacés intégralement. Les tests sont mis à jour en même temps.

---

### Étape 3.1 — `cube_client.py`

#### Protocol mis à jour

```python
class SupportsCubeQueries(Protocol):
    def list_views(self) -> dict[str, Any]: ...
    def get_view_schema(self, view_name: str) -> dict[str, Any]: ...
    def query_view(
        self,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        time_dimensions: list[dict[str, Any]] | None = None,
        order: dict[str, str] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]: ...
```

#### `list_views()` — filtre sur `type == "view"`

```python
def list_views(self) -> dict[str, Any]:
    meta = self._fetch_meta()
    # Cube retourne les views dans le même tableau "cubes" avec type="view"
    views = [c for c in meta.get("cubes", []) if c.get("type") == "view"]
    return {"cubes": views}
```

> Note : Cube expose les views dans `/v1/meta` avec `"type": "view"`. Avec `public: false` sur tous les cubes, seules les views apparaissent dans le tableau `cubes`. Le filtre est donc une sécurité supplémentaire.

#### `get_view_schema()` — enrichi

```python
def get_view_schema(self, view_name: str) -> dict[str, Any]:
    ...
    def _field(item: dict, is_measure: bool = False) -> dict:
        result = {
            "name": item["name"],
            "type": item.get("type", "unknown"),
            "description": item.get("description", ""),
        }
        if is_measure:
            result["additive"] = _is_additive(item.get("type", ""))
        else:
            result["is_calculated"] = _is_calculated(item.get("sql", ""))
        return result
    ...
```

Helpers :

```python
_NON_ADDITIVE_TYPES = {"avg", "count_distinct", "count_distinct_approx"}

def _is_additive(measure_type: str) -> bool:
    return measure_type not in _NON_ADDITIVE_TYPES

def _is_calculated(sql_expr: str) -> bool:
    """True si la dimension est le résultat d'une expression SQL (CASE, DATEDIFF, etc.)."""
    if not sql_expr:
        return False
    keywords = ("CASE", "DATEDIFF", "DATE_PART", "DATEADD", "CONCAT", "COALESCE", "NULLIF")
    return any(kw in sql_expr.upper() for kw in keywords)
```

#### `query_view()` — même comportement que `query_cube`, + `order`

```python
def query_view(
    self,
    measures: list[str],
    dimensions: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    time_dimensions: list[dict[str, Any]] | None = None,
    order: dict[str, str] | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    query = {
        "measures": measures,
        "dimensions": dimensions or [],
        "filters": filters or [],
        "timeDimensions": time_dimensions or [],
        "limit": limit,
    }
    if order:
        query["order"] = order
    # même corps que query_cube (POST /load)
    ...
```

> **Pourquoi `order` est ajouté** : les questions Q3, Q6, Q10 ont besoin de `ORDER BY` côté Cube pour le TOP-N. Le tool actuel `query_cube` n'expose pas ce paramètre. C'est le moment de l'ajouter.

---

### Étape 3.2 — `tools.py`

Trois tools renommés et enrichis.

#### `list_views` (remplace `list_cubes`)

```python
@tool
def list_views() -> str:
    """Return a lightweight list of all available views with one-line summaries.

    Each entry contains: name, summary.
    Call this first to identify which view(s) are relevant to the question,
    then call describe_view(view_name) for full member details before querying.
    """
    ...
    # Même logique que list_cubes mais sur client.list_views()
    # Extrait meta.summary (ou premier paragraphe de description)
```

#### `describe_view` (remplace `get_cube_schema`)

```python
@tool(args_schema=GetViewSchemaArgs)
def describe_view(view_name: str) -> str:
    """Return the full schema for a single view: description, measures, and dimensions.

    Each measure includes: name, type, description, additive (bool).
    Each dimension includes: name, type, description, is_calculated (bool).
    additive=False means the measure cannot be summed across sub-groupings (avg, count_distinct).
    is_calculated=True means the dimension uses a SQL expression (CASE WHEN, date functions, etc.).

    Call this after list_views() has identified the relevant view, and before
    calling query_view. Use only the member names this tool returns.

    Args:
        view_name: Exact view name as returned by list_views().
    """
```

#### `query_view` (remplace `query_cube`)

```python
@tool(args_schema=QueryViewArgs)
def query_view(
    view: str,
    measures: list[str],
    dimensions: list[str] = [],
    filters: list[CubeFilter] = [],
    time_dimensions: list[CubeTimeDimension] = [],
    order: dict[str, str] = {},
    limit: int = 1000,
) -> str:
    """Query a semantic view. Returns rows as a list of dicts.

    Args:
        view: View name (must match a name returned by list_views()).
        measures: Metric names prefixed with view name, e.g. ["orders_overview.count"].
        dimensions: Grouping axes, e.g. ["orders_overview.delivery_status"].
        filters: Row filters.
        time_dimensions: Time filter or grouping.
        order: Sort order dict, e.g. {"catalog_sales.total_revenue": "desc"}.
        limit: Maximum rows returned (default 1000, max 5000).

    Use only member names returned by describe_view(). Never invent metric names.
    """
```

> **Note sur le nommage des membres** : avec les views Cube, les membres sont préfixés du nom de la VIEW (ex: `orders_overview.count`), pas du cube source. Le LLM doit être guidé sur ce point dans le docstring et dans le prompt.

#### Pydantic models mis à jour

```python
class GetViewSchemaArgs(BaseModel):
    view_name: str = Field(description="Exact view name as returned by list_views().")

class QueryViewArgs(BaseModel):
    view: str = Field(description="View name.")
    measures: list[str] = Field(...)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[CubeFilter] = Field(default_factory=list)
    time_dimensions: list[CubeTimeDimension] = Field(default_factory=list)
    order: dict[str, str] = Field(default_factory=dict)
    limit: int = Field(default=1000, ge=1, le=5000)
```

---

### Étape 3.3 — `prompt.py`

Mise à jour complète du prompt système pour référencer :
1. Les **views** (pas les cubes)
2. Les **nouveaux noms de tools** (`list_views`, `describe_view`, `query_view`)
3. La logique de **routing view** (quelle view pour quelle question)
4. Le **nommage des membres** avec le préfixe de la view

Points clés à inclure dans le prompt :

```
## Schema Discovery
1. Deux étapes : list_views() pour voir les views disponibles, puis describe_view(view_name)
   pour les membres complets de la view pertinente.
2. Les noms de membres sont préfixés du nom de la view
   (ex: "orders_overview.count", pas "orders.count").

## Routing (quelle view choisir)
- Questions sur le volume de commandes, statut, livraison → orders_overview
- Questions sur les paiements, méthodes, montants encaissés → payments_overview
- Questions sur les revenus par catégorie, vendeur, produit → catalog_sales
- Questions sur la satisfaction client (review score) → reviews_overview
- Requêtes cross-grain (review score par catégorie) → non faisable en mode standard

## Mesures non-additives
Si describe_view retourne additive=False sur une mesure, ne jamais la sommer
manuellement. L'utiliser telle quelle ou en choisir une autre.
```

---

## Phase 4 — Mise à jour des tests

### Étape 4.1 — `tests/test_cube_model.py`

Adapter les tests existants + ajouter des tests sur les views.

#### Tests existants à conserver (inchangés)

- `test_all_cube_models_read_from_marts_not_raw` — ok
- `test_orders_cube_points_to_marts_and_has_primary_key_time_dimension` — ok
- `test_order_items_cube_points_to_marts_and_defines_total_revenue` — ok
- `test_all_join_targets_declare_a_primary_key` — ok
- `test_all_cube_models_have_meta_summary` — ok
- `test_order_items_joins_orders_on_order_id` — ok

#### Tests à ajouter sur les cubes enrichis

```python
def test_orders_cube_has_bidirectional_joins():
    orders = load_cube("cube/model/cubes/orders.yml")
    join_names = {j["name"] for j in (orders.get("joins") or [])}
    assert "order_reviews" in join_names, "orders must declare one_to_many join to order_reviews"
    assert "order_items" in join_names, "orders must declare one_to_many join to order_items"
    assert "order_payments" in join_names, "orders must declare one_to_many join to order_payments"
    # Vérifier la cardinalité des joins inverses
    joins_by_name = {j["name"]: j for j in (orders.get("joins") or [])}
    assert joins_by_name["order_reviews"]["relationship"] == "one_to_many"
    assert joins_by_name["order_items"]["relationship"] == "one_to_many"
    assert joins_by_name["order_payments"]["relationship"] == "one_to_many"

def test_orders_cube_has_delivery_status_and_delay_days():
    orders = load_cube("cube/model/cubes/orders.yml")
    dims = {d["name"]: d for d in orders["dimensions"]}
    assert "delivery_status" in dims
    assert dims["delivery_status"]["type"] == "string"
    assert "delay_days" in dims
    assert dims["delay_days"]["type"] == "number"
    measures = {m["name"]: m for m in orders["measures"]}
    assert "avg_delay_days" in measures
    assert measures["avg_delay_days"]["type"] == "avg"
    assert "delivered_count" in measures

def test_order_payments_has_multi_installment_members():
    payments = load_cube("cube/model/cubes/order_payments.yml")
    dims = {d["name"]: d for d in payments["dimensions"]}
    assert "is_multi_installment" in dims
    assert dims["is_multi_installment"]["type"] == "boolean"
    measures = {m["name"]: m for m in payments["measures"]}
    assert "count_multi_installment" in measures
    assert "avg_installments" in measures

def test_all_cubes_are_private():
    for path in sorted(CUBE_MODEL_DIR.glob("*.yml")):
        cube = load_cube(str(path.relative_to(ROOT)))
        assert cube.get("public") is False, (
            f"{path.name} is missing 'public: false'"
        )
```

#### Tests à ajouter sur les views

```python
CUBE_VIEWS_DIR = ROOT / "cube/model/views"

def load_view(path: str) -> dict:
    model = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    return model["views"][0]

def test_all_views_have_description_and_meta_summary():
    for path in sorted(CUBE_VIEWS_DIR.glob("*.yml")):
        if path.name == "example_view.yml":
            continue
        view = load_view(str(path.relative_to(ROOT)))
        assert view.get("description"), f"{path.name} is missing description"
        summary = (view.get("meta") or {}).get("summary")
        assert summary, f"{path.name} is missing meta.summary"

def test_orders_overview_exposes_delivery_status_and_review_score():
    view = load_view("cube/model/views/orders_overview.yml")
    all_includes = []
    for cube_entry in view["cubes"]:
        all_includes.extend(cube_entry.get("includes", []))
    assert "delivery_status" in all_includes
    assert "avg_review_score" in all_includes
    assert "count" in all_includes

def test_catalog_sales_exposes_english_category_name():
    view = load_view("cube/model/views/catalog_sales.yml")
    all_includes = []
    for cube_entry in view["cubes"]:
        all_includes.extend(cube_entry.get("includes", []))
    assert "product_category_name_english" in all_includes
    assert "total_revenue" in all_includes

def test_payments_overview_exposes_multi_installment_measures():
    view = load_view("cube/model/views/payments_overview.yml")
    all_includes = []
    for cube_entry in view["cubes"]:
        all_includes.extend(cube_entry.get("includes", []))
    assert "count_multi_installment" in all_includes
    assert "payment_value" in all_includes

def test_reviews_overview_does_not_expose_product_category():
    view = load_view("cube/model/views/reviews_overview.yml")
    all_includes = []
    for cube_entry in view["cubes"]:
        all_includes.extend(cube_entry.get("includes", []))
    assert "product_category_name_english" not in all_includes
    assert "avg_review_score" in all_includes
```

---

### Étape 4.2 — `pulsar-agent/tests/test_agent_tools.py`

Refonte complète : renommage des tools + ajout des tests sur les enrichissements.

#### `FakeCubeClient` mis à jour

```python
class FakeCubeClient:
    def __init__(self, metadata=None, rows=None):
        self.metadata = metadata or {"cubes": []}
        self.rows = rows or []
        self.list_views_calls = 0
        self.query_view_calls: list[dict] = []

    def list_views(self) -> dict:
        self.list_views_calls += 1
        return self.metadata

    def get_view_schema(self, view_name: str) -> dict:
        # même logique que get_cube_schema
        ...

    def query_view(self, measures, dimensions=None, filters=None,
                   time_dimensions=None, order=None, limit=1000):
        self.query_view_calls.append(...)
        return self.rows
```

#### Tests clés à écrire

```python
def test_list_views_tool_returns_summaries()
def test_describe_view_tool_returns_additive_flag_on_measures()
def test_describe_view_tool_returns_is_calculated_flag_on_dimensions()
def test_describe_view_tool_returns_error_with_hint_for_unknown_view()
def test_query_view_tool_passes_order_parameter()
def test_query_view_tool_validation_error_is_returned_to_llm()
def test_make_tools_returns_three_tools_with_correct_names()
    # → names == {"list_views", "describe_view", "query_view"}
```

---

### Étape 4.3 — `pulsar-agent/tests/test_agent_graph.py`

Mettre à jour les fixtures qui référencent les anciens noms de tools.

```python
# AVANT
AIMessage(content="", tool_calls=[_tool_call("list_cubes", {}, "c1")]),
ToolMessage(content=..., name="list_cubes"),

# APRÈS
AIMessage(content="", tool_calls=[_tool_call("list_views", {}, "c1")]),
ToolMessage(content=..., name="list_views"),
```

Idem pour `get_cube_schema` → `describe_view` et `query_cube` → `query_view`.

Mettre à jour `SAMPLE_QUERY_ARGS` pour inclure `view` et utiliser les noms de membres préfixés par la view :

```python
SAMPLE_QUERY_ARGS = {
    "view": "catalog_sales",
    "measures": ["catalog_sales.total_revenue"],
    "time_dimensions": [{"dimension": "catalog_sales.order_purchase_timestamp", "granularity": "month"}],
    "dimensions": [],
    "filters": [],
    "order": {},
    "limit": 1000,
}
```

---

## Phase 5 — Mise à jour de CLAUDE.md

Sections à mettre à jour :

1. **What This Repo Is** (intro) : mentionner views + mode standard/advanced
2. **Layer responsibilities** : renommer les tools dans le tableau
3. **pulsar-agent/src/pulsar_agent/tools.py internals** : réécrire avec les 3 nouveaux tools
4. **System prompt rules** : mettre à jour les noms de tools dans la description des phases
5. **Cube semantic models** : ajouter le tableau des views, adapter le tableau des cubes (mention `public: false`)
6. **Testing** : mettre à jour les exemples de test avec les nouveaux noms

---

## Ordre d'exécution recommandé

Le blocage principal est que **les cubes ne peuvent pas passer en `public: false` avant que les views existent** — sinon Cube ne renvoie plus rien et les tests échouent.

```
1. Enrichir orders.yml (Phase 1.2) :
   - Ajouter delay_days, delivery_status, is_delivered (dimensions calculées)
   - Ajouter avg_delay_days, delivered_count (mesures)
   - Ajouter les 3 joins bidirectionnels (Phase 1.4) : order_items, order_reviews, order_payments
2. Enrichir order_payments.yml (Phase 1.3) :
   - Ajouter is_multi_installment, count_multi_installment, avg_installments
3. Créer les 4 fichiers views (Phase 2) — sans encore passer les cubes en private
   └── Test smoke : curl /v1/meta → cubes ET views visibles
4. Passer tous les cubes en public: false (Phase 1.1)
   └── Vérifier : /v1/meta → seules les 4 views visible, plus de cubes bruts
5. ✅ Test d'intégrité live (anti-fan-out) :
   - orders_overview.count doit être stable avec/sans dimension order_items
6. Mettre à jour tous les tests Python (Phase 4) — en une seule passe
7. Lancer la suite complète : uv run pytest
8. Migrer cube_client.py (Phase 3.1)
9. Migrer tools.py (Phase 3.2)
10. Mettre à jour prompt.py (Phase 3.3)
11. Mettre à jour CLAUDE.md (Phase 5)
```

---

## Points ouverts / décisions reportées

| # | Point | Impact | Quand trancher |
|---|---|---|---|
| 1 | ~~Join traversal inverse~~ | ✅ **Résolu** : joins one_to_many ajoutés dans orders.yml (Étape 1.4) | — |
| 2 | **`meta.example_questions`** dans les views | Améliore le routing mais masque les capacités LLM | Après 1er run d'évaluation des 17 questions |
| 3 | **Snowflake date functions** (`DATEDIFF`, `DATEADD`) | Si Cube génère du SQL natif Snowflake, OK ; sinon adapter | Après déploiement des cubes enrichis, tester Q15/Q16 |
| 4 | **`geolocation` cube** | Non inclus dans les views (hors scope couverture standard) | À évaluer si des questions géo émergent |
| 5 | **`order` param dans `query_view`** | Cube supporte `order` dans `/v1/load` — vérifier la structure exacte du payload | Lors de l'implémentation de query_view |

---

## Critères de succès

### Modèle Cube
- [ ] `uv run pytest tests/test_cube_model.py` passe intégralement
- [ ] `/v1/meta` ne retourne que les 4 views (plus de cubes bruts)
- [ ] Test d'intégrité live OK : `orders_overview.count` stable avec/sans dimension `order_items`

### Agent Python
- [ ] `uv run pytest` passe intégralement (0 régression)
- [ ] Les 3 nouveaux tools ont les bons noms : `list_views`, `describe_view`, `query_view`
- [ ] `describe_view` retourne `additive: false` sur `avg_review_score`, `unique_customer_count`, `avg_delay_days`
- [ ] `describe_view` retourne `is_calculated: true` sur `delivery_status`, `delay_days`

### Qualité agent (évaluation manuelle)
- [ ] L'agent répond correctement aux 11 questions standard (Q1–Q10 + Q16) sans halluciner de noms de membres
- [ ] Le routing view est correct (bonne view choisie pour chaque question type)
- [ ] Q16 (livraison vs satisfaction) est résolue en mode standard grâce à `delivery_status`

---

*Plan basé sur [PLAN_V2.md](./PLAN_V2.md) et l'état du repo au 27 mai 2026.*
