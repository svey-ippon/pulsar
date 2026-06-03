-- Conformed product-category dimension.
-- Promotes the category-name translation lookup to a first-class dimension keyed
-- on the Portuguese category name (the natural key carried by products). The
-- English name is a category attribute, so it lives here, not on dim_products.
-- Built from the categories actually present on products (left-joined to the
-- translation) so every product category resolves to a dimension row.
with
    product_categories as (
        select distinct "PRODUCT_CATEGORY_NAME" as product_category_name
        from {{ source("silver", "products") }}
        where "PRODUCT_CATEGORY_NAME" is not null
    )

select
    pc.product_category_name,
    t."PRODUCT_CATEGORY_NAME_ENGLISH" as product_category_name_english,
    iff(
        t."PRODUCT_CATEGORY_NAME_ENGLISH" is not null, true, false
    ) as has_english_category
from product_categories as pc
left join
    {{ source("silver", "product_category_name_translation") }} as t
    on pc.product_category_name = t."PRODUCT_CATEGORY_NAME"
