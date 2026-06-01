1. "What are customers most unhappy about in their reviews?"

  The semantic view only exposes review_score (numeric) and derived flags like is_negative_review. Review comment text — review_comment_message and review_comment_title —
  was never promoted from Silver into the Gold layer and is absent from the semantic view entirely. The agent can tell you that negative reviews correlate with late
  deliveries, but it has zero access to the actual complaint text. This is a hard data gap, not a modeling issue.

-> Snowflake Intelligence state that no free-text review comment are available and propose other structured angles (categories with negative review rate, delivery status...) -> ok

-> Cube-core : TO TEST


  ---
  2. "How many orders were paid using both a credit card and a voucher?"

  The semantic view's payments table is at payment-row grain with payment_type as a categorical dimension. Answering this requires set-intersection logic: "find order_ids
  where the set of payment_types for that order contains both X and Y". That's a multi-row-per-group membership test — structurally incompatible with the column-centric,
  single-row-per-grain semantic model. There's no payment_type_combination dimension, no multi-method flag. The agent might try a query but it would either error or silently
  return wrong results (e.g. counting payment rows instead of orders).

-> Snowflake Intelligence write a valid query. Very good point
-> cube-core: it can't make an equivalent query with the provided tool (REST API). It may be possible using SQL API (not traightforward to implement)
