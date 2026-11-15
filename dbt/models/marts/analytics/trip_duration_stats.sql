-- One row per year x rider type x bike type: the shape of trip lengths.

with trips as (

    select * from {{ ref('fct_trips') }}

)

select
    year(started_date)                                              as ride_year,
    member_casual,
    rideable_type,
    count(*)                                                        as trips,
    round(avg(duration_minutes), 2)                                 as avg_minutes,
    {{ percentile_minutes(0.25) }}             as p25_minutes,
    {{ percentile_minutes(0.50) }}             as median_minutes,
    {{ percentile_minutes(0.75) }}             as p75_minutes,
    {{ percentile_minutes(0.90) }}             as p90_minutes,
    {{ percentile_minutes(0.95) }}             as p95_minutes,
    round(max(duration_minutes), 2)                                 as max_minutes,
    round(avg(case when duration_minutes < 10 then 1.0 else 0.0 end), 4)   as share_under_10_min,
    round(avg(case when duration_minutes > 30 then 1.0 else 0.0 end), 4)   as share_over_30_min
from trips
group by year(started_date), member_casual, rideable_type
