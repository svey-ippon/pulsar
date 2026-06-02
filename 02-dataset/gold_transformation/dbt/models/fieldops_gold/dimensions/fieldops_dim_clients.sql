-- Conformed client dimension: the contract-holding company — THE "customer"
-- of FieldOps (CV-2). Reached from the facts via DIM_SITES (snowflake).
select client_id, client_name, industry, contract_tier
from {{ source("fieldops_silver", "clients") }}
