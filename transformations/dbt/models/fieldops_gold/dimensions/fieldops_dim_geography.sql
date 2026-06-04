{{ config(alias="DIM_GEOGRAPHY") }}

-- Conformed fictional geography. Role-played as site location (via DIM_SITES)
-- and depot location (via DIM_TECHNICIANS).
select zip_code_prefix, city, state
from {{ ref("fieldops_geography") }}
