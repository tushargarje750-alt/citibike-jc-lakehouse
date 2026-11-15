-- One row per day: how many trips, who rode, how long, and what the weather was.

with trips as (

    select * from {{ ref('fct_trips') }}

),

daily as (

    select
        started_date                                                         as ride_date,
        count(*)                                                             as trips,
        sum(case when member_casual = 'member' then 1 else 0 end)            as member_trips,
        sum(case when member_casual = 'casual' then 1 else 0 end)            as casual_trips,
        sum(case when rideable_type = 'electric_bike' then 1 else 0 end)     as electric_trips,
        round(avg(duration_minutes), 2)                                      as avg_duration_minutes,
        {{ percentile_minutes(0.5) }}                   as median_duration_minutes,
        count(distinct start_station_id)                                     as active_start_stations
    from trips
    group by started_date

),

weather as (

    select * from {{ ref('dim_weather_daily') }}

)

select
    daily.ride_date,
    cast(date_trunc('month', daily.ride_date) as date)   as ride_month,
    year(daily.ride_date)                                as ride_year,
    weekday(daily.ride_date) + 1                         as day_of_week,     -- 1 = Monday ... 7 = Sunday
    date_format(daily.ride_date, 'EEEE')                 as day_name,
    weekday(daily.ride_date) >= 5                        as is_weekend,

    daily.trips,
    daily.member_trips,
    daily.casual_trips,
    round(daily.member_trips / daily.trips, 4)           as member_share,
    daily.electric_trips,
    round(daily.electric_trips / daily.trips, 4)         as electric_share,
    daily.avg_duration_minutes,
    daily.median_duration_minutes,
    daily.active_start_stations,

    weather.temperature_mean_c,
    weather.temperature_band,
    weather.precipitation_mm,
    weather.snowfall_cm,
    weather.weather_category,
    weather.is_wet_day,
    weather.is_snow_day

from daily
left join weather
    on weather.weather_date = daily.ride_date
