select
    p."PRODUCT_ID" as product_id,
    p."PRODUCT_CATEGORY_NAME" as product_category_name,
    t."PRODUCT_CATEGORY_NAME_ENGLISH" as product_category_name_english,
    p."PRODUCT_NAME_LENGHT" as product_name_length,
    p."PRODUCT_DESCRIPTION_LENGHT" as product_description_length,
    p."PRODUCT_PHOTOS_QTY" as product_photos_qty,
    p."PRODUCT_WEIGHT_G" as product_weight_g,
    p."PRODUCT_LENGTH_CM" as product_length_cm,
    p."PRODUCT_HEIGHT_CM" as product_height_cm,
    p."PRODUCT_WIDTH_CM" as product_width_cm,
    iff(
        t."PRODUCT_CATEGORY_NAME_ENGLISH" is not null, true, false
    ) as has_english_category
from {{ source("silver", "products") }} as p
left join
    {{ source("silver", "product_category_name_translation") }} as t
    on p."PRODUCT_CATEGORY_NAME" = t."PRODUCT_CATEGORY_NAME"
