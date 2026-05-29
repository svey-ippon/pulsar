with
    product_revenue as (
        select
            product_category_name_english,
            product_id,
            sum(item_revenue) as total_revenue,
            count(*) as item_count,
            count(distinct order_id) as order_count
        from {{ ref("fct_order_items") }}
        where order_status = 'delivered' and product_category_name_english is not null
        group by product_category_name_english, product_id
    )

select
    product_category_name_english,
    product_id,
    total_revenue,
    item_count,
    order_count,
    rank() over (
        partition by product_category_name_english order by total_revenue desc
    ) as category_revenue_rank
from product_revenue
