select
    s."SELLER_ID" as seller_id,
    s."SELLER_ZIP_CODE_PREFIX" as seller_zip_code_prefix,
    s."SELLER_CITY" as seller_city,
    s."SELLER_STATE" as seller_state,
    g.latitude as seller_latitude,
    g.longitude as seller_longitude
from {{ source("silver", "sellers") }} as s
left join
    {{ ref("dim_geolocation_zip_prefix") }} as g
    on s."SELLER_ZIP_CODE_PREFIX" = g.zip_code_prefix
