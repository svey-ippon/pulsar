-- Keys-only bridge resolving the order <-> category many-to-many, at
-- (order_id, product_category_name) grain. It exists so ORDER-LEVEL facts
-- (reviews, order counts) can be sliced by category WITHOUT item fan-out.
-- Category measures (revenue, item counts) deliberately do NOT live here: they
-- come from fct_order_items aggregated by product -> category.
-- allocation_weight = 1 / (#categories in the order) is the Kimball weighting
-- factor to allocate order-level measures across categories without double counting.
with
    order_category as (
        select distinct oi."ORDER_ID" as order_id, p.product_category_name
        from {{ source("silver", "order_items") }} as oi
        join {{ ref("dim_products") }} as p on oi."PRODUCT_ID" = p.product_id
        where p.product_category_name is not null
    ),

    category_counts as (
        select order_id, count(*) as category_count
        from order_category
        group by order_id
    )

select
    concat(oc.order_id, '::', oc.product_category_name) as order_category_key,
    oc.order_id,
    oc.product_category_name,
    1.0 / cc.category_count as allocation_weight
from order_category as oc
join category_counts as cc on oc.order_id = cc.order_id
