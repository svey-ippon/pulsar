with
    monthly as (
        select
            order_purchase_month,
            year(order_purchase_month) as revenue_year,
            month(order_purchase_month) as revenue_month_number,
            sum(item_revenue) as total_revenue,
            count(distinct order_id) as order_count
        from {{ ref("fct_order_items") }}
        where order_status = 'delivered'
        group by order_purchase_month
    )

select
    order_purchase_month,
    revenue_year,
    revenue_month_number,
    total_revenue,
    order_count,
    lag(total_revenue) over (order by order_purchase_month) as previous_month_revenue,
    total_revenue
    - lag(total_revenue) over (order by order_purchase_month) as revenue_growth,
    100.0
    * (total_revenue - lag(total_revenue) over (order by order_purchase_month))
    / nullif(
        lag(total_revenue) over (order by order_purchase_month), 0
    ) as revenue_growth_pct
from monthly
