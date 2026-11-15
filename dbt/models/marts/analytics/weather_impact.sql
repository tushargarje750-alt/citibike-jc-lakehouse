-- One row per temperature band x wet/dry x weekend/weekday: how weather moves ridership.
--
-- The system grew a lot over the years, so raw trip counts would mostly compare
-- early years with late years. To isolate the weather effect, each day is first
-- compared with the average day OF ITS OWN MONTH (ridership_index: 1.0 = a normal
-- day for that month, 0.6 = 40% fewer trips than normal).

with weather as (

    select * from {{ ref('dim_weather_daily') }}

),

daily as (

    select * from {{ ref('daily_ridership') }}

),

bounds as (

    select min(ride_date) as first_day, max(ride_date) as last_day from daily

),

-- every calendar day in the trip period, including any day with no trips at all
calendar as (

    select
        weather.weather_date,
        weather.temperature_band,
        weather.is_wet_day,
        weekday(weather.weather_date) >= 5      as is_weekend,
        coalesce(daily.trips, 0)                as trips,
        coalesce(daily.member_trips, 0)         as member_trips,
        coalesce(daily.casual_trips, 0)         as casual_trips
    from weather
    cross join bounds
    left join daily on daily.ride_date = weather.weather_date
    where weather.weather_date between bounds.first_day and bounds.last_day

),

indexed as (

    select
        *,
        trips / nullif(
            avg(trips) over (partition by cast(date_trunc('month', weather_date) as date)), 0
        ) as ridership_index
    from calendar

)

select
    temperature_band,
    is_wet_day,
    is_weekend,
    count(*)                               as days,
    sum(trips)                             as trips,
    round(avg(trips), 1)                   as avg_trips_per_day,
    round(avg(member_trips), 1)            as avg_member_trips_per_day,
    round(avg(casual_trips), 1)            as avg_casual_trips_per_day,
    round(avg(ridership_index), 3)         as avg_ridership_index
from indexed
group by temperature_band, is_wet_day, is_weekend
