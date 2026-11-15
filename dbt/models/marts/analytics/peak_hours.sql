-- One row per weekday x hour x rider type: when people ride.
-- avg_trips_per_day divides by the number of such weekdays in the data, so a
-- Monday 8 am figure is "trips in that hour on a typical Monday".

with trips as (

    select * from {{ ref('fct_trips') }}

),

days as (

    select
        day_of_week,
        count(distinct started_date) as days_observed
    from trips
    group by day_of_week

),

hourly as (

    select
        day_of_week,
        max(day_name)                     as day_name,
        max(is_weekend)                   as is_weekend,
        started_hour,
        member_casual,
        count(*)                          as trips,
        round(avg(duration_minutes), 2)   as avg_duration_minutes
    from trips
    group by day_of_week, started_hour, member_casual

)

select
    hourly.day_of_week,
    hourly.day_name,
    hourly.is_weekend,
    hourly.started_hour,
    hourly.member_casual,
    hourly.trips,
    days.days_observed,
    round(hourly.trips / days.days_observed, 1)   as avg_trips_per_day,
    hourly.avg_duration_minutes,
    dense_rank() over (
        partition by hourly.day_of_week, hourly.member_casual
        order by hourly.trips desc
    )                                             as hour_rank_in_day
from hourly
inner join days on days.day_of_week = hourly.day_of_week
