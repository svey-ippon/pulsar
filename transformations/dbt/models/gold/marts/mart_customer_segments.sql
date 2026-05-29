with
    customer_revenue as (
        select
            customer_unique_id,
            count(distinct order_id) as delivered_order_count,
            sum(item_revenue) as delivered_merchandise_revenue
        from {{ ref("fct_order_items") }}
        where order_status = 'delivered' and customer_unique_id is not null
        group by customer_unique_id
    ),

    segmented as (
        select
            case
                when delivered_order_count >= 2 then 'repeat' else 'one_time'
            end as customer_segment,
            count(*) as customer_count,
            sum(delivered_order_count) as delivered_order_count,
            sum(delivered_merchandise_revenue) as total_revenue
        from customer_revenue
        group by case when delivered_order_count >= 2 then 'repeat' else 'one_time' end
    )

select
    customer_segment,
    customer_count,
    delivered_order_count,
    total_revenue,
    100.0 * customer_count / nullif(sum(customer_count) over (), 0) as pct_customers,
    100.0 * total_revenue / nullif(sum(total_revenue) over (), 0) as pct_revenue
from segmented
