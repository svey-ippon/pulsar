with
    seller_orders as (
        select distinct order_id, seller_id, seller_state
        from {{ ref("fct_order_items") }}
        where seller_id is not null
    ),

    seller_revenue as (
        select
            seller_id,
            min(seller_state) as seller_state,
            sum(iff(order_status = 'delivered', item_revenue, 0)) as delivered_revenue,
            count(
                distinct iff(order_status = 'delivered', order_id, null)
            ) as delivered_order_count,
            count(*) as item_count
        from {{ ref("fct_order_items") }}
        where seller_id is not null
        group by seller_id
    ),

    seller_reviews as (
        select
            so.seller_id,
            avg(r.review_score) as avg_review_score,
            count(r.review_score) as review_count
        from seller_orders as so
        inner join {{ ref("fct_order_reviews") }} as r on so.order_id = r.order_id
        where r.review_score is not null
        group by so.seller_id
    ),

    seller_delivery as (
        select
            seller_id,
            avg(delay_days) as avg_delay_days,
            100.0
            * count_if(delivery_late_status = 'late')
            / nullif(count(*), 0) as late_delivery_rate
        from {{ ref("mart_seller_delivery_performance") }}
        group by seller_id
    )

select
    sr.seller_id,
    sr.seller_state,
    sr.delivered_revenue,
    100.0
    * sr.delivered_revenue
    / nullif(sum(sr.delivered_revenue) over (), 0) as pct_total_delivered_revenue,
    sr.delivered_order_count,
    sr.item_count,
    rv.avg_review_score,
    coalesce(rv.review_count, 0) as review_count,
    d.avg_delay_days,
    d.late_delivery_rate,
    row_number() over (order by sr.delivered_revenue desc, sr.seller_id) as revenue_rank
from seller_revenue as sr
left join seller_reviews as rv on sr.seller_id = rv.seller_id
left join seller_delivery as d on sr.seller_id = d.seller_id
