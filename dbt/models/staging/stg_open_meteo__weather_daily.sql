-- One row per day. Columns are renamed so the unit is part of the name.

with source as (

    select * from {{ source('citibike_bronze', 'weather_daily_raw') }}

)

select
    cast(date as date)       as weather_date,
    weather_code,
    temperature_2m_max       as temperature_max_c,
    temperature_2m_min       as temperature_min_c,
    temperature_2m_mean      as temperature_mean_c,
    precipitation_sum        as precipitation_mm,
    rain_sum                 as rain_mm,
    snowfall_sum             as snowfall_cm,
    precipitation_hours,
    wind_speed_10m_max       as wind_speed_max_kmh,
    wind_gusts_10m_max       as wind_gusts_max_kmh,
    _ingested_at
from source
