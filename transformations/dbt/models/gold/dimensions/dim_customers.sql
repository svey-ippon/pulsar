-- Conformed PHYSICAL customer dimension at customer_unique_id grain.
-- The source customers table is at order-scoped customer_id grain; we collapse it
-- to the physical customer. Olist exposes no stable customer attribute (geography
-- varies per order), so this dimension is deliberately thin: it is the conformed
-- anchor for distinct-customer analysis. The order-scoped customer_id and its
-- geography live on fct_orders.
select distinct "CUSTOMER_UNIQUE_ID" as customer_unique_id
from {{ source("silver", "customers") }}
where "CUSTOMER_UNIQUE_ID" is not null
