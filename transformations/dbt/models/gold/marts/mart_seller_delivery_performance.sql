select
    order_item_key as seller_delivery_key,
    order_id,
    order_item_id,
    seller_id,
    seller_city,
    seller_state,
    order_purchase_timestamp,
    order_purchase_month,
    delay_days,
    delivery_late_status,
    item_revenue,
    freight_value
from {{ ref("fct_order_items") }}
where order_status = 'delivered' and delay_days is not null
