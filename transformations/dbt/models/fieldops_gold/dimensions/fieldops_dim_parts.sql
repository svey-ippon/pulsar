{{ config(alias="DIM_PARTS") }}

-- Spare-parts catalogue. list_price stays in silver (line_amount on the fact
-- already carries the billed value).
select part_id, part_name, part_family
from {{ ref("fieldops_parts") }}
