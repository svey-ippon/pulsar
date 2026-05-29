select
    o."ORDER_ID" as order_id,
    o."CUSTOMER_ID" as customer_id,
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    c.customer_zip_code_prefix,
    c.customer_latitude,
    c.customer_longitude,
    o."ORDER_STATUS" as order_status,
    o."ORDER_PURCHASE_TIMESTAMP" as order_purchase_timestamp,
    cast(o."ORDER_PURCHASE_TIMESTAMP" as date) as order_purchase_date,
    date_trunc('MONTH', o."ORDER_PURCHASE_TIMESTAMP") as order_purchase_month,
    year(o."ORDER_PURCHASE_TIMESTAMP") as order_purchase_year,
    month(o."ORDER_PURCHASE_TIMESTAMP") as order_purchase_month_number,
    dayofweek(o."ORDER_PURCHASE_TIMESTAMP") as order_purchase_day_of_week,
    o."ORDER_APPROVED_AT" as order_approved_at,
    o."ORDER_DELIVERED_CARRIER_DATE" as order_delivered_carrier_date,
    o."ORDER_DELIVERED_CUSTOMER_DATE" as order_delivered_customer_date,
    o."ORDER_ESTIMATED_DELIVERY_DATE" as order_estimated_delivery_date,
    iff(o."ORDER_STATUS" = 'delivered', true, false) as is_delivered_status,
    iff(
        o."ORDER_DELIVERED_CUSTOMER_DATE" is not null, true, false
    ) as has_customer_delivery_date,
    datediff(
        'DAY', o."ORDER_PURCHASE_TIMESTAMP", o."ORDER_APPROVED_AT"
    ) as approval_delay_days,
    datediff(
        'DAY', o."ORDER_PURCHASE_TIMESTAMP", o."ORDER_DELIVERED_CUSTOMER_DATE"
    ) as purchase_to_delivery_days,
    datediff(
        'DAY', o."ORDER_ESTIMATED_DELIVERY_DATE", o."ORDER_DELIVERED_CUSTOMER_DATE"
    ) as delay_days,
    case
        when o."ORDER_DELIVERED_CUSTOMER_DATE" is null
        then 'not_delivered'
        when o."ORDER_DELIVERED_CUSTOMER_DATE" > o."ORDER_ESTIMATED_DELIVERY_DATE"
        then 'late'
        else 'on_time'
    end as delivery_late_status,
    case
        when o."ORDER_DELIVERED_CUSTOMER_DATE" is null
        then 'not_delivered'
        when o."ORDER_DELIVERED_CUSTOMER_DATE" <= o."ORDER_ESTIMATED_DELIVERY_DATE"
        then 'on_time'
        when
            o."ORDER_DELIVERED_CUSTOMER_DATE"
            <= dateadd('DAY', 7, o."ORDER_ESTIMATED_DELIVERY_DATE")
        then 'late'
        else 'very_late'
    end as delivery_status
from {{ source("silver", "orders") }} as o
left join {{ ref("dim_customers") }} as c on o."CUSTOMER_ID" = c.customer_id
