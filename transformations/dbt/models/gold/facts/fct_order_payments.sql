select
    concat(op."ORDER_ID", '-', op."PAYMENT_SEQUENTIAL") as order_payment_key,
    op."ORDER_ID" as order_id,
    op."PAYMENT_SEQUENTIAL" as payment_sequential,
    op."PAYMENT_TYPE" as payment_type,
    op."PAYMENT_INSTALLMENTS" as payment_installments,
    iff(op."PAYMENT_INSTALLMENTS" > 1, true, false) as is_multi_installment,
    case
        when op."PAYMENT_INSTALLMENTS" <= 1
        then 'single'
        when op."PAYMENT_INSTALLMENTS" between 2 and 3
        then '2_to_3'
        when op."PAYMENT_INSTALLMENTS" between 4 and 6
        then '4_to_6'
        when op."PAYMENT_INSTALLMENTS" between 7 and 12
        then '7_to_12'
        else '13_plus'
    end as installment_bucket,
    op."PAYMENT_VALUE" as payment_value,
    o.customer_id,
    o.customer_unique_id,
    o.customer_state,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_purchase_date,
    o.order_purchase_month,
    o.order_purchase_year
from {{ source("silver", "order_payments") }} as op
left join {{ ref("fct_orders") }} as o on op."ORDER_ID" = o.order_id
