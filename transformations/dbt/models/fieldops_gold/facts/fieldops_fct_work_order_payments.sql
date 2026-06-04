{{ config(alias="FCT_WORK_ORDER_PAYMENTS") }}

-- Payment fact: one row per (work_order_id x payment_sequence). Collected
-- cash settling the invoice (lines + call-out fee) with a collection lag —
-- NOT service revenue.
select
    work_order_id || '-' || payment_sequence as work_order_payment_key,
    work_order_id,
    payment_sequence,
    payment_method,
    paid_date as paid_date_key,
    payment_amount
from {{ ref("fieldops_payments") }}
