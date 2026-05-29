with
    customer_revenue as (
        select
            customer_unique_id,
            min(customer_state) as customer_state,
            count(distinct order_id) as delivered_order_count,
            sum(item_revenue) as delivered_merchandise_revenue
        from {{ ref("fct_order_items") }}
        where order_status = 'delivered' and customer_unique_id is not null
        group by customer_unique_id
    )

select
    customer_unique_id,
    customer_state,
    delivered_order_count,
    delivered_merchandise_revenue,
    row_number() over (
        order by delivered_merchandise_revenue desc, customer_unique_id
    ) as revenue_rank,
    ntile(5) over (
        order by delivered_merchandise_revenue desc, customer_unique_id
    ) as revenue_quintile,
    100.0
    * delivered_merchandise_revenue
    / nullif(sum(delivered_merchandise_revenue) over (), 0) as pct_total_revenue,
    100.0 * sum(delivered_merchandise_revenue) over (
        order by delivered_merchandise_revenue desc, customer_unique_id
        rows between unbounded preceding and current row
    )
    / nullif(
        sum(delivered_merchandise_revenue) over (), 0
    ) as cumulative_pct_total_revenue
from customer_revenue
