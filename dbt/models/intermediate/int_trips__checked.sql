-- Every staged trip, with its duration and a verdict.
--   rejection_reason is null  -> the trip is good and goes to fct_trips
--   rejection_reason is set   -> the trip goes to trips_quarantine
-- A trip gets the FIRST rule it breaks, in the order written below.

{% set area = var('service_area') %}

with trips as (

    select * from {{ ref('stg_citibike__trips') }}

),

measured as (

    select
        *,
        timestampdiff(SECOND, started_at, ended_at) as duration_seconds
    from trips

),

rule_checked as (

    select
        *,
        case
            when ride_id is null
                then 'missing_ride_id'
            when started_at is null or ended_at is null
                then 'invalid_timestamp'
            when duration_seconds <= 0
                then 'non_positive_duration'
            when duration_seconds < {{ var('min_trip_seconds') }}
                then 'duration_too_short'
            when duration_seconds > {{ var('max_trip_seconds') }}
                then 'duration_too_long'
            when start_station_id is null and start_station_name is null
                then 'missing_start_station'
            when member_casual is null or member_casual not in ('member', 'casual')
                then 'invalid_rider_type'
            when start_lat not between {{ area['min_lat'] }} and {{ area['max_lat'] }}
              or start_lng not between {{ area['min_lng'] }} and {{ area['max_lng'] }}
                then 'start_outside_service_area'
        end as rule_violation
    from measured

),

-- The same ride_id can appear more than once. Among the copies that passed every
-- rule, keep the most recently loaded one and reject the rest as duplicates.
ranked as (

    select
        *,
        row_number() over (
            partition by ride_id, (rule_violation is null)
            order by _ingested_at desc, _source_month desc, ended_at desc
        ) as _copy_number
    from rule_checked

)

select
    ride_id,
    rideable_type,
    member_casual,
    started_at,
    ended_at,
    duration_seconds,
    start_station_id,
    start_station_name,
    end_station_id,
    end_station_name,
    start_lat,
    start_lng,
    end_lat,
    end_lng,
    started_at_raw,
    ended_at_raw,
    _source_file,
    _source_month,
    _ingested_at,
    _ingest_run_id,
    coalesce(
        rule_violation,
        case when _copy_number > 1 then 'duplicate_ride_id' end
    ) as rejection_reason
from ranked
