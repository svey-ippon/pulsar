with
    sellers_by_order as (
        select
            order_id,
            count(distinct seller_id) as seller_count,
            listagg(distinct seller_state, ',') within group (
                order by seller_state
            ) as seller_states
        from {{ ref("fct_order_items") }}
        group by order_id
    )

select
    o.order_id,
    o.customer_unique_id,
    o.customer_state,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_purchase_month,
    o.delivery_late_status,
    o.delivery_status,
    o.delay_days,
    coalesce(s.seller_count, 0) as seller_count,
    iff(coalesce(s.seller_count, 0) > 1, true, false) as is_multi_seller_order,
    s.seller_states
from {{ ref("fct_orders") }} as o
left join sellers_by_order as s on o.order_id = s.order_id
