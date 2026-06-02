-- Client locations where interventions happen. Snowflaked to DIM_CLIENTS;
-- geography via DIM_GEOGRAPHY (site-location role).
select site_id, client_id, site_name, site_type, zip_code_prefix as site_zip_code_prefix
from {{ source("fieldops_silver", "sites") }}
