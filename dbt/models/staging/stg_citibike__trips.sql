-- One row per bronze trip row, with names kept, text trimmed and values typed.
-- No rows are removed for quality reasons here; that happens in int_trips__checked.

with source as (

    select * from {{ source('citibike_bronze', 'trips_raw') }}

),

-- A republished month is loaded into bronze a second time (bronze is append-only).
-- Keep only the rows that came from the newest version of each source file.
newest_file_version as (

    select
        *,
        max(_source_file_modified_at) over (partition by _source_file) as _newest_file_modified_at
    from source

),

typed as (

    select
        nullif(trim(ride_id), '')                    as ride_id,
        nullif(lower(trim(rideable_type)), '')       as rideable_type,
        nullif(lower(trim(member_casual)), '')       as member_casual,

        try_cast(started_at as timestamp)            as started_at,
        try_cast(ended_at as timestamp)              as ended_at,

        nullif(trim(start_station_id), '')           as start_station_id,
        nullif(trim(start_station_name), '')         as start_station_name,
        nullif(trim(end_station_id), '')             as end_station_id,
        nullif(trim(end_station_name), '')           as end_station_name,

        try_cast(start_lat as double)                as start_lat,
        try_cast(start_lng as double)                as start_lng,
        try_cast(end_lat as double)                  as end_lat,
        try_cast(end_lng as double)                  as end_lng,

        -- original text of the timestamps, kept so rejected rows can be diagnosed
        started_at                                   as started_at_raw,
        ended_at                                     as ended_at_raw,

        _source_file,
        _source_month,
        _ingested_at,
        _ingest_run_id

    from newest_file_version
    where _source_file_modified_at = _newest_file_modified_at

)

select * from typed
