-- Review fact at (review_id, order_id) grain. Thin Kimball fact: keys + degenerate
-- dimensions + measures. Reviews are order-level. is_negative_review and
-- delivery-to-review timing are derived downstream; order/delivery attributes are
-- reached via fct_orders.
select
    concat(r."REVIEW_ID", '::', r."ORDER_ID") as order_review_key,

    -- foreign keys
    r."ORDER_ID" as order_id,
    cast(r."REVIEW_CREATION_DATE" as date) as review_creation_date_key,
    cast(r."REVIEW_ANSWER_TIMESTAMP" as date) as review_answer_date_key,

    -- degenerate dimensions
    r."REVIEW_ID" as review_id,
    r."REVIEW_COMMENT_TITLE" as review_comment_title,
    r."REVIEW_COMMENT_MESSAGE" as review_comment_message,

    -- measure
    r."REVIEW_SCORE" as review_score
from {{ source("silver", "order_reviews") }} as r
