-- Seller dimension. Geography is snowflaked to dim_geography (referenced via
-- seller_zip_code_prefix); city/state/coordinates are no longer carried inline.
select "SELLER_ID" as seller_id, "SELLER_ZIP_CODE_PREFIX" as seller_zip_code_prefix
from {{ source("silver", "sellers") }}
