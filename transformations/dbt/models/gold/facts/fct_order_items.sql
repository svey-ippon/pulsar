-- Order-item fact at (order_id, order_item_id) grain. Thin Kimball fact: keys +
-- degenerate dimensions + measures. Product, seller, order, customer, category and
-- date attributes are reached through the conformed dimensions, not denormalized.
select
    concat(oi."ORDER_ID", '-', oi."ORDER_ITEM_ID") as order_item_key,

    -- foreign keys
    oi."ORDER_ID" as order_id,
    oi."PRODUCT_ID" as product_id,
    oi."SELLER_ID" as seller_id,
    cast(oi."SHIPPING_LIMIT_DATE" as date) as shipping_limit_date_key,

    -- degenerate dimension
    oi."ORDER_ITEM_ID" as order_item_id,

    -- measures
    oi."PRICE" as item_revenue,
    oi."FREIGHT_VALUE" as freight_value
from {{ source("silver", "order_items") }} as oi
