-- FieldOps conformed date dimension (date spine over the 2017-2019 window,
-- with margin for payment/survey lags). Role-played by the six work-order
-- milestone keys plus the payment and survey date keys.
with
    spine as (
        {{
            dbt_utils.date_spine(
                datepart="day",
                start_date="to_date('2017-01-01', 'YYYY-MM-DD')",
                end_date="to_date('2021-01-01', 'YYYY-MM-DD')",
            )
        }}
    )

select
    cast(date_day as date) as date_day,
    year(date_day) as year,
    quarter(date_day) as quarter,
    month(date_day) as month_number,
    monthname(date_day) as month_name,
    date_trunc('month', date_day) as month_start_date,
    day(date_day) as day_of_month,
    dayofweek(date_day) as day_of_week,
    dayname(date_day) as day_name,
    weekofyear(date_day) as week_of_year,
    iff(dayofweek(date_day) in (0, 6), true, false) as is_weekend
from spine
