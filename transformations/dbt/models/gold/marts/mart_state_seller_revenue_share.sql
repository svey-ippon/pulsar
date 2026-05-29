with
    seller_state_revenue as (
        select
            customer_state,
            seller_id,
            min(seller_state) as seller_state,
            sum(item_revenue) as seller_revenue,
            count(distinct order_id) as order_count
        from {{ ref("fct_order_items") }}
        where
            order_status = 'delivered'
            and customer_state is not null
            and seller_id is not null
        group by customer_state, seller_id
    )

select
    customer_state,
    seller_id,
    seller_state,
    seller_revenue,
    order_count,
    100.0
    * seller_revenue
    / nullif(
        sum(seller_revenue) over (partition by customer_state), 0
    ) as pct_customer_state_revenue,
    row_number() over (
        partition by customer_state order by seller_revenue desc, seller_id
    ) as seller_rank_in_customer_state
from seller_state_revenue
