-- One row per month x rider type: how members and casual riders differ, and how that changes.

with trips as (

    select * from {{ ref('fct_trips') }}

),

monthly as (

    select
        cast(date_trunc('month', started_date) as date)                          as ride_month,
        member_casual,
        count(*)                                                                 as trips,
        round(avg(duration_minutes), 2)                                          as avg_duration_minutes,
        {{ percentile_minutes(0.5) }}                       as median_duration_minutes,
        round(avg(case when rideable_type = 'electric_bike' then 1.0 else 0.0 end), 4) as electric_share,
        round(avg(case when is_weekend then 1.0 else 0.0 end), 4)                as weekend_share,
        round(avg(case when is_round_trip then 1.0 else 0.0 end), 4)             as round_trip_share,
        count(distinct started_date)                                             as active_days
    from trips
    group by cast(date_trunc('month', started_date) as date), member_casual

)

select
    ride_month,
    member_casual,
    trips,
    round(trips / sum(trips) over (partition by ride_month), 4)   as share_of_month_trips,
    round(trips / active_days, 1)                                 as avg_trips_per_day,
    avg_duration_minutes,
    median_duration_minutes,
    electric_share,
    weekend_share,
    round_trip_share
from monthly
