with
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
    z.zip_code_prefix, c.city, c.state, z.latitude, z.longitude, z.geolocation_row_count
from zip_centroids as z
left join
    city_candidates as c
    on z.zip_code_prefix = c.zip_code_prefix
    and c.city_state_rank = 1
