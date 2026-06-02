-- Equipment category referential. Individual units stay in silver; work orders
-- reach categories through BRIDGE_WORK_ORDER_CATEGORIES.
select equipment_category, category_group
from {{ source("fieldops_silver", "equipment_categories") }}
