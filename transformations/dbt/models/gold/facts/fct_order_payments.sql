-- Payment fact at (order_id, payment_sequential) grain. Thin Kimball fact:
-- keys + degenerate dimensions + measures. Installment banding and order/customer
-- attributes are derived downstream / reached via conformed dimensions.
select
    concat(op."ORDER_ID", '-', op."PAYMENT_SEQUENTIAL") as order_payment_key,

    -- foreign key
    op."ORDER_ID" as order_id,

    -- degenerate dimensions
    op."PAYMENT_SEQUENTIAL" as payment_sequential,
    op."PAYMENT_TYPE" as payment_type,

    -- measures
    op."PAYMENT_INSTALLMENTS" as payment_installments,
    op."PAYMENT_VALUE" as payment_value
from {{ source("silver", "order_payments") }} as op
