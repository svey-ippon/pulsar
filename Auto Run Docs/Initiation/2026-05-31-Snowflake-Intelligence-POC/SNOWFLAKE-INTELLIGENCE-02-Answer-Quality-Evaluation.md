# Phase 02: Answer Quality Evaluation Template

This phase creates the structured evaluation document for Snowflake Intelligence, mirroring the existing Pulsar Cube evaluation at `docs/evaluation/pulsar_cube/PULSAR_CUBE_QUESTION_EVALUATION.md`. The output is a pre-populated template with all 16 benchmark questions (S1–S5, M1–M5+M4b, C1–C5) ready to be filled in by running each question against Snowflake Intelligence in Snowsight and recording the response quality. The template structure enables direct side-by-side comparison with the Pulsar Cube evaluation.

## Tasks

- [ ] Create `docs/evaluation/snowflake_intelligence/` folder and write `SNOWFLAKE_INTELLIGENCE_QUESTION_EVALUATION.md`. The file must follow the exact structure of `docs/evaluation/pulsar_cube/PULSAR_CUBE_QUESTION_EVALUATION.md` (read it first for exact formatting patterns). The document should contain:

  **Header section:**
  ```markdown
  # Snowflake Intelligence Question Evaluation

  This document evaluates Snowflake Intelligence (Cortex AI via Snowsight) against the Olist benchmark catalog.

  Reference catalog: [QUESTION_CATALOG.md](../QUESTION_CATALOG.md)
  Pulsar Cube baseline: [PULSAR_CUBE_QUESTION_EVALUATION.md](../pulsar_cube/PULSAR_CUBE_QUESTION_EVALUATION.md)

  Evaluation setup:
  - Semantic View: `ECOMMERCE_DB.GOLD.OLIST_ANALYTICS`
  - Interface: Snowflake Intelligence in Snowsight
  - Each question is asked as a natural language prompt with no SQL
  ```

  **Expected Coverage Summary table** (pre-populated with the semantic objects that should cover each question based on the Semantic View design):

  | ID | Expected coverage | Primary semantic table | Notes |
  |---|---|---|---|
  | S1 | Should answer | `orders` | `order_count` metric, no filter |
  | S2 | Should answer | `orders` or `customers` | `customer_unique_id` disambiguation needed |
  | S3 | Should answer | `payments` | `payment_type` dimension, `payment_count` metric |
  | S4 | Should answer | `reviews` | `average_review_score` metric |
  | S5 | Should answer with caveat | `payments` | `collected_value` vs `merchandise_revenue` disambiguation |
  | M1 | Should answer | `order_items` | `merchandise_revenue` by `product_category_name_english` |
  | M2 | Should answer | `order_items` or `monthly_revenue` | time bucketing on `order_purchase_month` |
  | M3a | Should answer | `payments` | `multi_installment_payment_share` metric |
  | M3b | Should answer | `payments` | distinct order count with installments > 1 |
  | M4 | Should ask for clarification | `order_items` or `seller_scorecard` | metric ambiguity test |
  | M4b | Should answer | `order_items` | ratio metric + HAVING equivalent |
  | M5 | Should answer | `category_satisfaction` | dedicated fan-out-safe mart |
  | C1 | Should answer | `product_category_revenue_rank` or `order_items` | top-N per partition |
  | C2 | Should answer | `customer_cohorts` | dedicated cohort mart |
  | C3 | Should answer | `seller_delivery_performance` | dedicated delivery performance mart |
  | C4 | Should answer | `reviews` + `orders` | `delivery_late_status` dimension |
  | C5 | Should answer | `customer_segments` | dedicated segmentation mart |

  **Question Coverage section** — one subsection per question using this template for each:

  ```markdown
  ### S1 - Total Number Of Orders

  **Question asked in Snowflake Intelligence:** How many orders are in the database?

  **Expected result:** ~99,441 orders (all statuses, no filter).

  **Snowflake Intelligence response:**
  > _[Paste response here]_

  **Generated SQL or query plan (if shown):**
  ```sql
  -- [Paste if available]
  ```

  **Score:** _[0 / 1 / 2]_ — _[0=wrong, 1=partial or wrong assumption, 2=correct and well explained]_

  **Notes:** _[Observations about the response: did it apply a delivered filter? Did it ask a clarifying question? Did it hallucinate?]_

  ---
  ```

  Create this template block for all 16 questions: S1, S2, S3, S4, S5, M1, M2, M3a, M3b, M4, M4b, M5, C1, C2, C3, C4, C5. Populate the **Expected result** field for each from the question catalog at `docs/evaluation/QUESTION_CATALOG.md`. Leave **Snowflake Intelligence response**, **Generated SQL**, **Score**, and **Notes** blank for the evaluator to fill in.

  **Scoring Summary section** at the bottom:

  ```markdown
  ## Scoring Summary

  | ID | Difficulty | Score | Notes |
  |---|---|---|---|
  | S1 | Simple | | |
  | S2 | Simple | | |
  | S3 | Simple | | |
  | S4 | Simple | | |
  | S5 | Simple | | |
  | M1 | Medium | | |
  | M2 | Medium | | |
  | M3a | Medium | | |
  | M3b | Medium | | |
  | M4 | Medium | | |
  | M4b | Medium | | |
  | M5 | Advanced | | |
  | C1 | Advanced | | |
  | C2 | Advanced | | |
  | C3 | Advanced | | |
  | C4 | Advanced | | |
  | C5 | Advanced | | |
  | **Total** | | **/34** | |

  ## Comparison With Pulsar Cube

  | Category | Pulsar Cube | Snowflake Intelligence |
  |---|---|---|
  | Simple (S1–S5, 10 pts max) | 10/10 | _/10 |
  | Medium (M1–M5+M4b, 12 pts max) | 12/12 | _/12 |
  | Advanced (C1–C5, 10 pts max) | 10/10 | _/10 |
  | **Total** | **32+/34** | **_/34** |
  ```

- [ ] Update `docs/evaluation/GLOBAL_REVIEW.md` to add a Snowflake Intelligence row in any comparison tables, referencing `[[SNOWFLAKE_INTELLIGENCE_QUESTION_EVALUATION]]`. Read the current file first to determine the correct insertion point and table structure.
