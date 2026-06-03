-- Product dimension. Physical attributes only; category identity/translation is
-- snowflaked out to dim_categories (referenced via product_category_name).
select
    "PRODUCT_ID" as product_id,
    "PRODUCT_CATEGORY_NAME" as product_category_name,
    "PRODUCT_NAME_LENGHT" as product_name_length,
    "PRODUCT_DESCRIPTION_LENGHT" as product_description_length,
    "PRODUCT_PHOTOS_QTY" as product_photos_qty,
    "PRODUCT_WEIGHT_G" as product_weight_g,
    "PRODUCT_LENGTH_CM" as product_length_cm,
    "PRODUCT_HEIGHT_CM" as product_height_cm,
    "PRODUCT_WIDTH_CM" as product_width_cm
from {{ source("silver", "products") }}
