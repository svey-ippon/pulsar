{{ config(alias="FCT_WORK_ORDER_LINES") }}

-- Intervention line fact: one row per (work_order_id x line_number).
-- PART lines carry part_id/quantity; LABOR lines carry billed_hours
-- (part_id NULL — meaningful NULL). line_amount is the billed value of the
-- line; service revenue = SUM(line_amount) + call-out fees (CV-1).
select
    work_order_id || '-' || line_number as work_order_line_key,
    work_order_id,
    line_number,
    line_kind,
    part_id,
    quantity,
    billed_hours,
    line_amount
from {{ ref("fieldops_work_order_lines") }}
