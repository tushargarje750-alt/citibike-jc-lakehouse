-- One row per station, ranked by the number of trips that started there.

with trips as (

    select * from {{ ref('fct_trips') }}

),

stations as (

    select * from {{ ref('dim_stations') }}

),

starts as (

    select
        start_station_id                                              as station_id,
        count(*)                                                      as trips_started,
        sum(case when member_casual = 'member' then 1 else 0 end)     as member_trips_started,
        sum(case when is_round_trip then 1 else 0 end)                as round_trips,
        round(avg(duration_minutes), 2)                               as avg_duration_minutes,
        count(distinct started_date)                                  as active_days
    from trips
    where start_station_id is not null
    group by start_station_id

),

ends as (

    select
        end_station_id      as station_id,
        count(*)            as trips_ended
    from trips
    where end_station_id is not null
    group by end_station_id

)

select
    stations.station_id,
    stations.station_name,
    stations.area,
    stations.latitude,
    stations.longitude,

    coalesce(starts.trips_started, 0)                                        as trips_started,
    coalesce(ends.trips_ended, 0)                                            as trips_ended,
    coalesce(starts.trips_started, 0) - coalesce(ends.trips_ended, 0)        as net_departures,   -- positive: more bikes leave than arrive
    round(starts.member_trips_started / starts.trips_started, 4)             as member_share_of_starts,
    round(starts.round_trips / starts.trips_started, 4)                      as round_trip_share,
    starts.avg_duration_minutes,
    starts.active_days,
    round(starts.trips_started / starts.active_days, 1)                      as avg_starts_per_active_day,

    dense_rank() over (order by coalesce(starts.trips_started, 0) desc)      as start_rank

from stations
left join starts on starts.station_id = stations.station_id
left join ends   on ends.station_id = stations.station_id
