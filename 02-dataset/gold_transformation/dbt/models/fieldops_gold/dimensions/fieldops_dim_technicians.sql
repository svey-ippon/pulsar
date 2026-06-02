-- Technician (crew lead) dimension. Depot carried as attributes; depot
-- geography via DIM_GEOGRAPHY (depot-location role).
select
    t.technician_id,
    t.depot_code,
    d.zip_code_prefix as depot_zip_code_prefix,
    t.seniority_level
from {{ source("fieldops_silver", "technicians") }} as t
left join {{ source("fieldops_silver", "depots") }} as d on t.depot_code = d.depot_code
