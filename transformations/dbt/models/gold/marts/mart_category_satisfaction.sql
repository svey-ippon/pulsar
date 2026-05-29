select
    concat(
        b.order_id, '::', b.product_category_name_english, '::', r.review_id
    ) as category_review_key,
    b.order_id,
    r.review_id,
    b.product_category_name_english,
    b.customer_state,
    b.order_status,
    b.order_purchase_timestamp,
    b.order_purchase_month,
    b.order_purchase_year,
    b.category_merchandise_revenue,
    r.review_score,
    r.is_negative_review
from {{ ref("bridge_order_categories") }} as b
inner join {{ ref("fct_order_reviews") }} as r on b.order_id = r.order_id
where r.review_score is not null
