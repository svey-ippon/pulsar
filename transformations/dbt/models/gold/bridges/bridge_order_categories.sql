select
    concat(order_id, '::', product_category_name_english) as order_category_key,
    order_id,
    product_category_name_english,
    min(order_purchase_timestamp) as order_purchase_timestamp,
    min(order_purchase_month) as order_purchase_month,
    min(order_purchase_year) as order_purchase_year,
    min(order_status) as order_status,
    min(customer_state) as customer_state,
    count(*) as item_count_in_category,
    sum(item_revenue) as category_merchandise_revenue
from {{ ref("fct_order_items") }}
where product_category_name_english is not null
group by order_id, product_category_name_english
