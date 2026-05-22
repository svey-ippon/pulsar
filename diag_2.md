```text
cube-1  | Performing query: 3e0ad2b3-cb48-4ce7-a2fd-147b2e7d530b-span-1
cube-1  | Executing SQL: 3e0ad2b3-cb48-4ce7-a2fd-147b2e7d530b-span-1
cube-1  | --
cube-1  |   SELECT
cube-1  |       "products"."PRODUCT_CATEGORY_NAME" "products__product_category_name", sum("order_items"."PRICE") "order_items__total_revenue"
cube-1  |     FROM
cube-1  |       ECOMMERCE_DB.MARTS.ORDER_ITEMS AS "order_items"
cube-1  | LEFT JOIN ECOMMERCE_DB.MARTS.PRODUCTS AS "products" ON "order_items"."PRODUCT_ID" = "products"."PRODUCT_ID"  GROUP BY 1 ORDER BY 2 DESC LIMIT 10
cube-1  | --
cube-1  | Performing query completed: 3e0ad2b3-cb48-4ce7-a2fd-147b2e7d530b-span-1 (2394ms)
cube-1  | Load Request Success: 3e0ad2b3-cb48-4ce7-a2fd-147b2e7d530b-span-1 (2450ms)
cube-1  | --
cube-1  | {
cube-1  |   "measures": [
cube-1  |     "order_items.total_revenue"
cube-1  |   ],
cube-1  |   "dimensions": [
cube-1  |     "products.product_category_name"
cube-1  |   ],
cube-1  |   "filters": [],
cube-1  |   "timeDimensions": [],
cube-1  |   "limit": 10,
cube-1  |   "cacheMode": "stale-if-slow",
cube-1  |   "timezone": "UTC"
cube-1  | }
cube-1  | --
cube-1  | Performing query: scheduler-43ee0182-7cb7-40b3-a380-6ecfebfd0d65
cube-1  | Executing SQL: scheduler-43ee0182-7cb7-40b3-a380-6ecfebfd0d65
cube-1  | --
cube-1  |   SELECT FLOOR((UNIX_TIMESTAMP()) / 120) as refresh_key
cube-1  | --
cube-1  | Performing query completed: scheduler-43ee0182-7cb7-40b3-a380-6ecfebfd0d65 (2ms)
```
