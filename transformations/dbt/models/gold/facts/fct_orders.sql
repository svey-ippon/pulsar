-- Order fact at order_id grain. Pure-Kimball thin fact: keys + degenerate
-- dimensions + measures only. Customer/geography/date attributes are reached
-- through the conformed dimensions, not denormalized here.
-- customer_unique_id and customer_zip_code_prefix come from the source customers
-- table (order-scoped customer_id -> physical customer + per-order geography).
select
    o."ORDER_ID" as order_id,

    -- foreign keys
    c."CUSTOMER_UNIQUE_ID" as customer_unique_id,
    c."CUSTOMER_ZIP_CODE_PREFIX" as customer_zip_code_prefix,
    cast(o."ORDER_PURCHASE_TIMESTAMP" as date) as order_purchase_date_key,
    cast(o."ORDER_APPROVED_AT" as date) as order_approved_date_key,
    cast(o."ORDER_DELIVERED_CARRIER_DATE" as date) as order_delivered_carrier_date_key,
    cast(
        o."ORDER_DELIVERED_CUSTOMER_DATE" as date
    ) as order_delivered_customer_date_key,
    cast(
        o."ORDER_ESTIMATED_DELIVERY_DATE" as date
    ) as order_estimated_delivery_date_key,

    -- degenerate dimensions
    o."CUSTOMER_ID" as customer_id,
    o."ORDER_STATUS" as order_status,
    o."ORDER_PURCHASE_TIMESTAMP" as order_purchase_timestamp,

    -- measures
    datediff(
        'DAY', o."ORDER_ESTIMATED_DELIVERY_DATE", o."ORDER_DELIVERED_CUSTOMER_DATE"
    ) as delay_days,
    datediff(
        'DAY', o."ORDER_PURCHASE_TIMESTAMP", o."ORDER_APPROVED_AT"
    ) as approval_delay_days,
    datediff(
        'DAY', o."ORDER_PURCHASE_TIMESTAMP", o."ORDER_DELIVERED_CUSTOMER_DATE"
    ) as purchase_to_delivery_days
from {{ source("silver", "orders") }} as o
left join {{ source("silver", "customers") }} as c on o."CUSTOMER_ID" = c."CUSTOMER_ID"
