with
    customer_orders as (
        select
            customer_unique_id,
            min(order_purchase_timestamp) as first_order_timestamp,
            max(order_purchase_timestamp) as last_order_timestamp,
            count(distinct order_id) as order_count,
            count(
                distinct iff(order_status = 'delivered', order_id, null)
            ) as delivered_order_count,
            min(customer_state) as customer_state
        from {{ ref("fct_orders") }}
        where customer_unique_id is not null
        group by customer_unique_id
    ),

    customer_revenue as (
        select
            customer_unique_id,
            sum(
                iff(order_status = 'delivered', item_revenue, 0)
            ) as delivered_merchandise_revenue
        from {{ ref("fct_order_items") }}
        where customer_unique_id is not null
        group by customer_unique_id
    ),

    customer_reviews as (
        select
            customer_unique_id,
            avg(review_score) as avg_review_score,
            count(*) as review_count,
            count_if(is_negative_review) as negative_review_count
        from {{ ref("fct_order_reviews") }}
        where customer_unique_id is not null and review_score is not null
        group by customer_unique_id
    ),

    as_of_date as (
        select max(order_purchase_date) as max_order_purchase_date
        from {{ ref("fct_orders") }}
    )

select
    o.customer_unique_id,
    o.customer_state,
    o.first_order_timestamp,
    o.last_order_timestamp,
    datediff(
        'DAY', cast(o.last_order_timestamp as date), a.max_order_purchase_date
    ) as days_since_last_order,
    o.order_count,
    o.delivered_order_count,
    coalesce(r.delivered_merchandise_revenue, 0) as delivered_merchandise_revenue,
    rv.avg_review_score,
    coalesce(rv.review_count, 0) as review_count,
    coalesce(rv.negative_review_count, 0) as negative_review_count,
    case
        when
            datediff(
                'DAY', cast(o.last_order_timestamp as date), a.max_order_purchase_date
            )
            >= 180
            and coalesce(rv.avg_review_score, 5) <= 3
        then 'at_risk'
        when o.delivered_order_count >= 2
        then 'repeat'
        else 'one_time'
    end as customer_health_segment
from customer_orders as o
cross join as_of_date as a
left join customer_revenue as r on o.customer_unique_id = r.customer_unique_id
left join customer_reviews as rv on o.customer_unique_id = rv.customer_unique_id
