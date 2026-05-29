select
    concat(r."REVIEW_ID", '::', r."ORDER_ID") as order_review_key,
    r."REVIEW_ID" as review_id,
    r."ORDER_ID" as order_id,
    r."REVIEW_SCORE" as review_score,
    iff(r."REVIEW_SCORE" <= 2, true, false) as is_negative_review,
    r."REVIEW_COMMENT_TITLE" as review_comment_title,
    r."REVIEW_COMMENT_MESSAGE" as review_comment_message,
    r."REVIEW_CREATION_DATE" as review_creation_date,
    r."REVIEW_ANSWER_TIMESTAMP" as review_answer_timestamp,
    datediff(
        'DAY', o.order_delivered_customer_date, r."REVIEW_CREATION_DATE"
    ) as delivery_to_review_days,
    o.customer_id,
    o.customer_unique_id,
    o.customer_state,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_purchase_month,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    o.delay_days,
    o.delivery_late_status,
    o.delivery_status
from {{ source("silver", "order_reviews") }} as r
left join {{ ref("fct_orders") }} as o on r."ORDER_ID" = o.order_id
