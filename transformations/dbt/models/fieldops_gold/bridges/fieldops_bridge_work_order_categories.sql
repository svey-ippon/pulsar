{{ config(alias="BRIDGE_WORK_ORDER_CATEGORIES") }}

-- Keys-only weighted bridge: one row per (work_order_id x equipment_category),
-- derived from the equipment units each work order serviced (silver-only).
-- allocation_weight = 1 / #distinct categories in the WO: slicing work-order
-- measures by category REQUIRES the weight, otherwise multi-category WOs are
-- double-counted.
with
    wo_categories as (
        select distinct s.work_order_id, u.equipment_category
        from {{ ref("fieldops_work_order_servicing") }} as s
        inner join
            {{ ref("fieldops_equipment_units") }} as u
            on s.equipment_unit_id = u.equipment_unit_id
    )

select
    work_order_id,
    equipment_category,
    1.0 / count(*) over (partition by work_order_id) as allocation_weight
from wo_categories
