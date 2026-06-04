{{ config(alias="DIM_TECHNICIANS") }}

-- Technician (crew lead) dimension. Depot carried as attributes (the Olist
-- DIM_SELLER pattern); depot geography via DIM_GEOGRAPHY (depot-location role).
select
    t.technician_id,
    t.depot_code,
    d.zip_code_prefix as depot_zip_code_prefix,
    t.seniority_level
from {{ ref("fieldops_technicians") }} as t
left join {{ ref("fieldops_depots") }} as d on t.depot_code = d.depot_code
