-- Conformed geography dimension at zip-code-prefix grain (was
-- dim_geolocation_zip_prefix).
-- Covers EVERY zip prefix referenced anywhere in the model (geolocation + customers +
-- sellers), so all customer/seller foreign keys resolve. City/state/centroid come from
-- the raw geolocation rows where available; some Olist zip prefixes have no geolocation
-- row, so those attributes are null for them.
-- Role-played as customer location (fct_orders) and seller location (dim_sellers).
with
    all_zips as (
        select distinct "GEOLOCATION_ZIP_CODE_PREFIX" as zip_code_prefix
        from {{ source("silver", "geolocation") }}
        where "GEOLOCATION_ZIP_CODE_PREFIX" is not null
        union
        select distinct "CUSTOMER_ZIP_CODE_PREFIX" as zip_code_prefix
        from {{ source("silver", "customers") }}
        where "CUSTOMER_ZIP_CODE_PREFIX" is not null
        union
        select distinct "SELLER_ZIP_CODE_PREFIX" as zip_code_prefix
        from {{ source("silver", "sellers") }}
        where "SELLER_ZIP_CODE_PREFIX" is not null
    ),

    zip_centroids as (
        select
            "GEOLOCATION_ZIP_CODE_PREFIX" as zip_code_prefix,
            avg("GEOLOCATION_LAT") as latitude,
            avg("GEOLOCATION_LNG") as longitude,
            count(*) as geolocation_row_count
        from {{ source("silver", "geolocation") }}
        where "GEOLOCATION_ZIP_CODE_PREFIX" is not null
        group by "GEOLOCATION_ZIP_CODE_PREFIX"
    ),

    city_candidates as (
        select
            "GEOLOCATION_ZIP_CODE_PREFIX" as zip_code_prefix,
            "GEOLOCATION_CITY" as city,
            "GEOLOCATION_STATE" as state,
            count(*) as city_state_row_count,
            row_number() over (
                partition by "GEOLOCATION_ZIP_CODE_PREFIX"
                order by count(*) desc, "GEOLOCATION_STATE", "GEOLOCATION_CITY"
            ) as city_state_rank
        from {{ source("silver", "geolocation") }}
        where "GEOLOCATION_ZIP_CODE_PREFIX" is not null
        group by "GEOLOCATION_ZIP_CODE_PREFIX", "GEOLOCATION_CITY", "GEOLOCATION_STATE"
    )

select
    a.zip_code_prefix,
    c.city,
    c.state,
    z.latitude,
    z.longitude,
    coalesce(z.geolocation_row_count, 0) as geolocation_row_count
from all_zips as a
left join zip_centroids as z on a.zip_code_prefix = z.zip_code_prefix
left join
    city_candidates as c
    on a.zip_code_prefix = c.zip_code_prefix
    and c.city_state_rank = 1
