with
    customer_orders as (
        select
            customer_unique_id,
            order_id,
            order_purchase_timestamp,
            min(order_purchase_timestamp) over (
                partition by customer_unique_id
            ) as first_order_timestamp
        from {{ ref("fct_orders") }}
        where customer_unique_id is not null
    ),

    customer_flags as (
        select
            customer_unique_id,
            date_trunc('MONTH', first_order_timestamp) as cohort_month,
            max(
                iff(
                    order_purchase_timestamp > first_order_timestamp
                    and datediff('DAY', first_order_timestamp, order_purchase_timestamp)
                    <= 90,
                    1,
                    0
                )
            ) as retained_90d_flag,
            max(
                iff(
                    order_purchase_timestamp > first_order_timestamp
                    and datediff('DAY', first_order_timestamp, order_purchase_timestamp)
                    <= 180,
                    1,
                    0
                )
            ) as retained_180d_flag
        from customer_orders
        group by customer_unique_id, date_trunc('MONTH', first_order_timestamp)
    )

select
    cohort_month,
    year(cohort_month) as cohort_year,
    month(cohort_month) as cohort_month_number,
    count(*) as cohort_size,
    sum(retained_90d_flag) as retained_90d,
    100.0 * sum(retained_90d_flag) / nullif(count(*), 0) as retention_90d_pct,
    sum(retained_180d_flag) as retained_180d,
    100.0 * sum(retained_180d_flag) / nullif(count(*), 0) as retention_180d_pct
from customer_flags
group by cohort_month
