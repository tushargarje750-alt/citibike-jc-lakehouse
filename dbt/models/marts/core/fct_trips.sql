{{
    config(
        materialized='incremental',
        unique_key='ride_id',
        incremental_strategy='merge',
        on_schema_change='append_new_columns',
        liquid_clustered_by=['started_date']
    )
}}

-- One row per good trip: typed, deduplicated, with the day's weather attached.
--
-- Incremental: after the first build, only bronze rows loaded since the previous
-- run are processed, and they are merged in on ride_id (new rides are inserted,
-- a ride that arrives again replaces its earlier row).

with trips as (

    select * from {{ ref('int_trips__checked') }}
    where rejection_reason is null
    {% if is_incremental() %}
      and _ingested_at > (
          select coalesce(max(_ingested_at), timestamp '1900-01-01') from {{ this }}
      )
    {% endif %}

),

weather as (

    select * from {{ ref('dim_weather_daily') }}

)

select
    trips.ride_id,
    trips.rideable_type,
    trips.member_casual,

    trips.started_at,
    trips.ended_at,
    cast(trips.started_at as date)                        as started_date,
    hour(trips.started_at)                                as started_hour,
    weekday(trips.started_at) + 1                         as day_of_week,      -- 1 = Monday ... 7 = Sunday
    date_format(trips.started_at, 'EEEE')                 as day_name,
    weekday(trips.started_at) >= 5                        as is_weekend,

    trips.duration_seconds,
    round(trips.duration_seconds / 60.0, 2)               as duration_minutes,

    trips.start_station_id,
    trips.start_station_name,
    trips.end_station_id,
    trips.end_station_name,
    trips.end_station_id is not null                      as has_end_station,
    coalesce(trips.start_station_id = trips.end_station_id, false) as is_round_trip,

    trips.start_lat,
    trips.start_lng,
    trips.end_lat,
    trips.end_lng,

    weather.temperature_mean_c,
    weather.temperature_band,
    weather.precipitation_mm,
    weather.snowfall_cm,
    weather.wind_speed_max_kmh,
    weather.weather_category,
    weather.is_wet_day,

    trips._source_month,
    trips._ingested_at

from trips
left join weather
    on weather.weather_date = cast(trips.started_at as date)
