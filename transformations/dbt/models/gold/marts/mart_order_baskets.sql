with
    item_agg as (
        select
            order_id,
            count(*) as item_count,
            count(distinct product_id) as product_count,
            count(distinct seller_id) as seller_count,
            sum(item_revenue) as merchandise_revenue,
            sum(freight_value) as freight_value
        from {{ ref("fct_order_items") }}
        group by order_id
    ),

    payment_agg as (
        select
            order_id,
            sum(payment_value) as collected_value,
            count(*) as payment_row_count,
            max(payment_installments) as max_payment_installments,
            count_if(is_multi_installment) as multi_installment_payment_rows
        from {{ ref("fct_order_payments") }}
        group by order_id
    )

select
    o.order_id,
    o.customer_id,
    o.customer_unique_id,
    o.customer_state,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_purchase_date,
    o.order_purchase_month,
    o.order_purchase_year,
    o.delivery_late_status,
    o.delivery_status,
    o.delay_days,
    coalesce(i.item_count, 0) as item_count,
    coalesce(i.product_count, 0) as product_count,
    coalesce(i.seller_count, 0) as seller_count,
    iff(coalesce(i.seller_count, 0) > 1, true, false) as is_multi_seller_order,
    coalesce(i.merchandise_revenue, 0) as merchandise_revenue,
    coalesce(i.freight_value, 0) as freight_value,
    coalesce(i.merchandise_revenue, 0)
    + coalesce(i.freight_value, 0) as order_value_with_freight,
    coalesce(p.collected_value, 0) as collected_value,
    coalesce(p.payment_row_count, 0) as payment_row_count,
    p.max_payment_installments,
    coalesce(p.multi_installment_payment_rows, 0) as multi_installment_payment_rows
from {{ ref("fct_orders") }} as o
left join item_agg as i on o.order_id = i.order_id
left join payment_agg as p on o.order_id = p.order_id
