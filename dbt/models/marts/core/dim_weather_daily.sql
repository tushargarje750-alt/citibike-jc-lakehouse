-- One row per day: the weather, plus a few labels that make it easy to group trips by.

with weather as (

    select * from {{ ref('stg_open_meteo__weather_daily') }}

)

select
    weather_date,

    temperature_min_c,
    temperature_max_c,
    temperature_mean_c,
    round(temperature_mean_c * 9 / 5 + 32, 1) as temperature_mean_f,
    case
        when temperature_mean_c is null then null
        when temperature_mean_c < 0  then 'freezing'
        when temperature_mean_c < 10 then 'cold'
        when temperature_mean_c < 20 then 'mild'
        when temperature_mean_c < 27 then 'warm'
        else 'hot'
    end as temperature_band,

    precipitation_mm,
    rain_mm,
    snowfall_cm,
    precipitation_hours,
    coalesce(precipitation_mm >= 1.0, false) as is_wet_day,
    coalesce(snowfall_cm > 0, false)         as is_snow_day,

    wind_speed_max_kmh,
    wind_gusts_max_kmh,

    weather_code,
    -- WMO weather interpretation codes, grouped
    case
        when weather_code is null            then null
        when weather_code = 0                then 'clear'
        when weather_code in (1, 2, 3)       then 'cloudy'
        when weather_code in (45, 48)        then 'fog'
        when weather_code between 51 and 57  then 'drizzle'
        when weather_code between 61 and 67  then 'rain'
        when weather_code between 71 and 77  then 'snow'
        when weather_code between 80 and 82  then 'rain'
        when weather_code in (85, 86)        then 'snow'
        when weather_code between 95 and 99  then 'thunderstorm'
        else 'other'
    end as weather_category

from weather
