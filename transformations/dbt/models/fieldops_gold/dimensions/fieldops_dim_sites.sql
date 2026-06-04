{{ config(alias="DIM_SITES") }}

-- Client locations where interventions happen. Snowflaked to DIM_CLIENTS
-- (the Olist product -> category pattern); geography via DIM_GEOGRAPHY
-- (site-location role).
select site_id, client_id, site_name, site_type, zip_code_prefix as site_zip_code_prefix
from {{ ref("fieldops_sites") }}
