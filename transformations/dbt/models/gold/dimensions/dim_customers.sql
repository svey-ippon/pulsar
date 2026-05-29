select
    c."CUSTOMER_ID" as customer_id,
    c."CUSTOMER_UNIQUE_ID" as customer_unique_id,
    c."CUSTOMER_ZIP_CODE_PREFIX" as customer_zip_code_prefix,
    c."CUSTOMER_CITY" as customer_city,
    c."CUSTOMER_STATE" as customer_state,
    g.latitude as customer_latitude,
    g.longitude as customer_longitude
from {{ source("silver", "customers") }} as c
left join
    {{ ref("dim_geolocation_zip_prefix") }} as g
    on c."CUSTOMER_ZIP_CODE_PREFIX" = g.zip_code_prefix
