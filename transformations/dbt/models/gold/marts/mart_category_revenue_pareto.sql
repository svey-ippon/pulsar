with
    category_revenue as (
        select
            product_category_name_english,
            sum(item_revenue) as total_revenue,
            count(distinct order_id) as order_count
        from {{ ref("fct_order_items") }}
        where order_status = 'delivered' and product_category_name_english is not null
        group by product_category_name_english
    )

select
    product_category_name_english,
    total_revenue,
    order_count,
    row_number() over (
        order by total_revenue desc, product_category_name_english
    ) as revenue_rank,
    100.0 * total_revenue / nullif(sum(total_revenue) over (), 0) as pct_total_revenue,
    100.0 * sum(total_revenue) over (
        order by total_revenue desc, product_category_name_english
        rows between unbounded preceding and current row
    )
    / nullif(sum(total_revenue) over (), 0) as cumulative_pct_total_revenue
from category_revenue
