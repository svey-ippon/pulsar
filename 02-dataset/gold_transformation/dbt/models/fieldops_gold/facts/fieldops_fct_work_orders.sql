-- Work-order fact: accumulating snapshot, one row per work_order_id. Pure
-- Kimball thin fact: keys + degenerate dimensions + measures. Client and
-- geography attributes are reached via DIM_SITES / DIM_TECHNICIANS.
--
-- sla_delay_bdays is PRECOMPUTED here (spec principle 2): signed count of
-- business days (Mon-Fri, no holiday calendar) in [promised_date,
-- completed_date) — same semantics as numpy.busday_count in the generator.
-- NULL = not completed. Late (CV-3) = sla_delay_bdays > 2.
with
    work_orders as (select * from {{ source("fieldops_silver", "work_orders") }}),

    busday_delay as (
        select
            wo.work_order_id,
            iff(wo.completed_date >= wo.promised_date, 1, -1)
            * count(d.date_day) as sla_delay_bdays
        from work_orders as wo
        inner join
            {{ ref("fieldops_dim_date") }} as d
            on d.date_day >= least(wo.promised_date, wo.completed_date)
            and d.date_day < greatest(wo.promised_date, wo.completed_date)
            and not d.is_weekend
        where wo.completed_date is not null
        group by wo.work_order_id, iff(wo.completed_date >= wo.promised_date, 1, -1)
    )

select
    wo.work_order_id,

    -- foreign keys
    wo.site_id,
    wo.technician_id,
    wo.opened_date as opened_date_key,
    wo.promised_date as promised_date_key,
    wo.scheduled_date as scheduled_date_key,
    wo.started_date as started_date_key,
    wo.completed_date as completed_date_key,
    wo.validated_date as validated_date_key,

    -- degenerate dimensions
    wo.work_order_type,
    wo.priority,
    wo.crew_size,

    -- measures
    iff(
        wo.completed_date is not null, coalesce(b.sla_delay_bdays, 0), null
    ) as sla_delay_bdays,
    wo.duration_hours,
    wo.call_out_fee
from work_orders as wo
left join busday_delay as b on wo.work_order_id = b.work_order_id
