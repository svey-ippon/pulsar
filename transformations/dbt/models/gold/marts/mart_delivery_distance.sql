select
    order_item_key,
    order_id,
    order_item_id,
    seller_id,
    seller_state,
    customer_state,
    order_status,
    order_purchase_timestamp,
    order_purchase_month,
    item_revenue,
    freight_value,
    delay_days,
    delivery_late_status,
    seller_latitude,
    seller_longitude,
    customer_latitude,
    customer_longitude,
    case
        when
            seller_latitude is null
            or seller_longitude is null
            or customer_latitude is null
            or customer_longitude is null
        then null
        else
            2
            * 6371
            * asin(
                least(
                    1,
                    sqrt(
                        power(sin(radians(customer_latitude - seller_latitude) / 2), 2)
                        + cos(radians(seller_latitude))
                        * cos(radians(customer_latitude))
                        * power(
                            sin(radians(customer_longitude - seller_longitude) / 2), 2
                        )
                    )
                )
            )
    end as seller_customer_distance_km
from {{ ref("fct_order_items") }}
where seller_id is not null and customer_id is not null
