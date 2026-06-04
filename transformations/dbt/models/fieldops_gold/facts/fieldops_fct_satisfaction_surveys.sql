{{ config(alias="FCT_SATISFACTION_SURVEYS") }}

-- Satisfaction survey fact: one row per survey RESPONSE — several responses
-- per work order are possible (re-surveys). Grain convention: the LATEST
-- response (highest response_sequence) is the one that counts per work order.
select
    work_order_id || '-' || response_sequence as survey_response_key,
    work_order_id,
    response_sequence,
    responded_date as responded_date_key,
    satisfaction_score
from {{ ref("fieldops_surveys") }}
