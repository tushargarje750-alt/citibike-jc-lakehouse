-- One row per station that appears in a good trip, as a start or as an end.
-- Station names and coordinates drift a little over the years, so the most
-- recent name and the median coordinates are used.

with trips as (

    select * from {{ ref('int_trips__checked') }}
    where rejection_reason is null

),

station_events as (

    select
        start_station_id   as station_id,
        start_station_name as station_name,
        start_lat          as latitude,
        start_lng          as longitude,
        started_at         as seen_at,
        1                  as is_start
    from trips
    where start_station_id is not null

    union all

    select
        end_station_id,
        end_station_name,
        end_lat,
        end_lng,
        ended_at,
        0
    from trips
    where end_station_id is not null

)

select
    station_id,
    max_by(station_name, seen_at)                 as station_name,
    count(distinct station_name)                  as name_variants,
    case
        when station_id like 'JC%' then 'Jersey City'
        when station_id like 'HB%' then 'Hoboken'
        else 'Outside JC/Hoboken'
    end                                           as area,
    round(percentile_approx(latitude, 0.5), 6)    as latitude,
    round(percentile_approx(longitude, 0.5), 6)   as longitude,
    cast(min(seen_at) as date)                    as first_seen_date,
    cast(max(seen_at) as date)                    as last_seen_date,
    sum(is_start)                                 as trips_started,
    sum(1 - is_start)                             as trips_ended
from station_events
group by station_id
