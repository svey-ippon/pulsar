with
    order_payment_profile as (
        select
            order_id,
            max(payment_installments) as max_payment_installments,
            sum(payment_value) as collected_value
        from {{ ref("fct_order_payments") }}
        group by order_id
    ),

    order_profile as (
        select
            p.order_id,
            case
                when p.max_payment_installments <= 1
                then 'single'
                when p.max_payment_installments between 2 and 3
                then '2_to_3'
                when p.max_payment_installments between 4 and 6
                then '4_to_6'
                when p.max_payment_installments between 7 and 12
                then '7_to_12'
                else '13_plus'
            end as max_installment_bucket,
            p.max_payment_installments,
            p.collected_value,
            r.review_score,
            r.is_negative_review
        from order_payment_profile as p
        left join {{ ref("fct_order_reviews") }} as r on p.order_id = r.order_id
    )

select
    max_installment_bucket,
    count(distinct order_id) as order_count,
    avg(max_payment_installments) as avg_max_installments,
    avg(collected_value) as avg_collected_value,
    sum(collected_value) as total_collected_value,
    count(review_score) as review_count,
    avg(review_score) as avg_review_score,
    100.0
    * count_if(is_negative_review)
    / nullif(count(review_score), 0) as negative_review_rate
from order_profile
group by max_installment_bucket
