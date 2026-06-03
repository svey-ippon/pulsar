# Olist gold — target model (pure Kimball star)

> **Status: draft / proposal.** Companion to `olist_gold_target.dbml`. Defines the gold layer we
> want *before* writing a clean semantic contract on top of it. The current gold (see
> `olist_sales.dbml` / `olist_sales.yaml`) is a denormalized hybrid; this is the redesign.
>
> **Decisions made:** philosophy = **pure Kimball star** (facts = keys + degenerate dims + measures
> only; *no* denormalized attributes — the explicit goal is to stress-test the agent's joins).
> Scope = **Tier 1 + Tier 2**. Tier 3 is documented (§6), not built.

Source of truth for available columns: the dbt project at `repos/transformations/dbt/models`
(silver sources + current gold models). This redesign re-shapes those same inputs.

---

## 1. Why redesign

The current gold is convenient but not exemplary: attributes are denormalized onto every fact
(e.g. `FCT_ORDER_ITEMS` recopies ~25 customer/seller/order/date columns), there is no date or
geography dimension, the customer dimension is at the wrong grain, and the "bridge" is a hybrid
that carries measures and has no real second side. A clean contract needs a clean model.

## 2. The conformed-dimension bus matrix

| Fact \ Dimension          | DIM_DATE (role-play)        | DIM_CUSTOMER | DIM_GEOGRAPHY (role-play) | DIM_PRODUCT | DIM_CATEGORY | DIM_SELLER |
|---------------------------|-----------------------------|:------------:|:-------------------------:|:-----------:|:------------:|:----------:|
| FCT_ORDERS                | purchase/approved/carrier/delivered/estimated | ✅ | customer | — | — | — |
| FCT_ORDER_ITEMS           | shipping_limit              | (via order)  | (seller via DIM_SELLER)   | ✅          | (via product)| ✅         |
| FCT_ORDER_PAYMENTS        | (via order)                 | (via order)  | —                         | —           | —            | —          |
| FCT_ORDER_REVIEWS         | review_created/answered     | (via order)  | —                         | —           | —            | —          |
| BRIDGE_ORDER_CATEGORY     | —                           | —            | —                         | —           | ✅           | (order)    |

Conformance is the point: one `DIM_DATE`, one `DIM_GEOGRAPHY`, one physical `DIM_CUSTOMER` shared
across the model — instead of truncated date columns and state strings copied onto every fact.

## 3. Dimensions

- **DIM_DATE** *(new)* — grain: one calendar day, key `DATE_DAY`. Built from a generated date spine.
  **Role-played** by every date FK (5 roles on orders, 1 on items, 2 on reviews). Replaces all the
  per-fact `..._DATE` / `..._MONTH` / `..._YEAR` / `day_of_week` truncations.
- **DIM_CUSTOMER** *(regrained)* — grain `CUSTOMER_UNIQUE_ID` (the **physical** customer). Was
  `dim_customers` at `customer_id` (order-scoped) grain — the root cause of the
  `COUNT(DISTINCT customer_unique_id)` gymnastics. Deliberately **thin**: Olist has no stable
  customer attribute, and geography varies per order, so it lives at order grain via DIM_GEOGRAPHY.
  The order-scoped `customer_id` becomes a **degenerate dimension** on `FCT_ORDERS`.
- **DIM_GEOGRAPHY** *(renamed)* — grain `ZIP_CODE_PREFIX` (was `dim_geolocation_zip_prefix`, already
  built). City/state/centroid lat-lng. **Role-played** as customer location (`FCT_ORDERS`) and
  seller location (`DIM_SELLER`). Removes geography duplication across customers, sellers and 4 facts.
- **DIM_CATEGORY** *(new)* — grain `PRODUCT_CATEGORY_NAME` (Portuguese, natural key) + English
  translation. Promotes `product_category_name_translation` to a conformed dimension. The English
  name is a **category** attribute, so it is snowflaked **out** of `DIM_PRODUCT`.
- **DIM_PRODUCT** *(trimmed)* — grain `PRODUCT_ID`; FK to `DIM_CATEGORY`; physical attributes
  (weight, dims, photos, name/desc length). English category removed.
- **DIM_SELLER** *(trimmed)* — grain `SELLER_ID`; FK to `DIM_GEOGRAPHY`. city/state/lat/lng removed.

## 4. Facts (thin)

Every fact now holds only **keys + degenerate dimensions + measures**.

- **FCT_ORDERS** — grain `ORDER_ID`. FKs: `CUSTOMER_UNIQUE_ID`→DIM_CUSTOMER,
  `CUSTOMER_ZIP_CODE_PREFIX`→DIM_GEOGRAPHY, 5 date roles→DIM_DATE. Degenerate: `ORDER_ID`,
  `CUSTOMER_ID`, `ORDER_STATUS`, `ORDER_PURCHASE_TIMESTAMP` (kept for intra-day/recency).
  Measures: `DELAY_DAYS`, `APPROVAL_DELAY_DAYS`, `PURCHASE_TO_DELIVERY_DAYS`.
- **FCT_ORDER_ITEMS** — grain `(order_id, order_item_id)`. FKs: PRODUCT, SELLER, shipping_limit→DATE.
  Measures: `ITEM_REVENUE`, `FREIGHT_VALUE`.
- **FCT_ORDER_PAYMENTS** — grain `(order_id, payment_sequential)`. Degenerate: `PAYMENT_TYPE`,
  `PAYMENT_SEQUENTIAL`. Measures: `PAYMENT_VALUE`, `PAYMENT_INSTALLMENTS`.
- **FCT_ORDER_REVIEWS** — grain `(review_id, order_id)`. FKs: review_created/answered→DATE.
  Measure: `REVIEW_SCORE`. Degenerate text: comment title/message (optional).

## 5. The bridge becomes a real bridge

`BRIDGE_ORDER_CATEGORY` — grain `(order_id, category)`, **keys only**:
`ORDER_ID`→FCT_ORDERS, `PRODUCT_CATEGORY_NAME`→**DIM_CATEGORY** (a genuine second side now that the
category dimension exists), plus an `ALLOCATION_WEIGHT = 1 / (#categories in the order)` — the
textbook Kimball weighting factor that lets order-level measures be allocated across categories
without double counting. **Measures removed**: `category_merchandise_revenue` / `item_count` were
duplicating `FCT_ORDER_ITEMS` aggregates; merchandise revenue by category comes from items →
product → category. The bridge exists only to slice **order-grain** facts (reviews, order counts)
by category without item fan-out.

## 6. Derivations moved OUT of gold (Tier 2)

These were stored columns; they become certified-metric expressions or query-time logic, documented
in the semantic contract rather than materialized:

| Removed column | Lived on | Re-expressed as |
|---|---|---|
| `delivery_status` (on_time/late/very_late/not_delivered) | orders | derived from `DELAY_DAYS`: null→not_delivered, ≤0→on_time, 1–7→late, >7→very_late |
| `delivery_late_status` | orders | derived from `DELAY_DAYS` sign + null |
| `is_delivered_status`, `has_customer_delivery_date` | orders | `ORDER_STATUS='delivered'` / delivered-date not null |
| `order_purchase_date/month/year/day_of_week/month_number` | every fact | DIM_DATE attributes |
| `item_value_with_freight` | items | `ITEM_REVENUE + FREIGHT_VALUE` |
| `installment_bucket`, `is_multi_installment` | payments | banded from `PAYMENT_INSTALLMENTS` (a band dim or CASE) |
| `is_negative_review` | reviews | `REVIEW_SCORE <= 2` |
| `delivery_to_review_days` | reviews | cross-fact: review_created − order_delivered (join) |
| `category_merchandise_revenue`, `item_count_in_category` | bridge | `FCT_ORDER_ITEMS` aggregate by category |
| `customer_city/state/zip/lat/lng`, `seller_city/state/...` denormalized onto facts | items/payments/reviews/orders | DIM_GEOGRAPHY / DIM_CUSTOMER joins |

## 7. Tier 3 — documented, not built (what it would buy)

- **Integer surrogate keys + SCD on dimensions.** Today dims key on natural hashes and are
  implicitly SCD Type 1 (history overwritten). Surrogate keys decouple gold from source, speed up
  joins, and—paired with effective-dating—enable **SCD Type 2** so a seller relocation or product
  recategorization preserves history. *Buys:* correct point-in-time attribution; *costs:* surrogate
  pipeline + the agent must join on keys, not natural ids.
- **Junk dimension** for the low-cardinality flags (`order_status`, `payment_type`, plus the derived
  delivery/installment bands). *Buys:* fewer degenerate columns, a tidy place for flag combinations;
  *costs:* an extra join for what are cheap inline attributes at this scale.
- **DIM_TIME (time-of-day).** If intra-day analysis ever matters, split the kept timestamps into a
  date FK + a time-of-day dimension. *Buys:* clean hour/shift analysis; *costs:* rarely needed here.
- **Confirm `FCT_ORDER_REVIEWS` grain.** Verify review↔order is strictly 1:1 in the data; if a
  review can span orders (or vice versa), state the M2M explicitly rather than relying on the
  synthetic key. *Buys:* certainty on dedup rules; *costs:* a data-profiling check.

## 8. Impact downstream

- **dbt**: add `dim_date` (date spine) and `dim_category`; regrain `dim_customers`→`dim_customer`;
  rename `dim_geolocation_zip_prefix`→`dim_geography`; strip denormalized columns from the 4 facts;
  rebuild `bridge_order_categories`→`bridge_order_category` (keys-only + weight). Marts may need
  rework where they read removed columns.
- **Semantic contract** (`olist_sales.yaml` + the SEMANTIC_*.md set): rewritten on the clean star —
  more `relationships` now carry real signal (joins are mandatory, not optional denorm shortcuts),
  and the Tier-2 derivations become `certified_metrics` / `sql_generation_rules`.
