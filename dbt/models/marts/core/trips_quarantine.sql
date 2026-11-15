-- Every bronze trip row that was NOT accepted into fct_trips, with the reason.
-- Nothing is silently dropped: bronze rows = fct_trips rows + rows in this table.
-- Rebuilt in full on every run so it always reflects the current rules.

select
    ride_id,
    rejection_reason,
    started_at_raw,
    ended_at_raw,
    started_at,
    ended_at,
    duration_seconds,
    rideable_type,
    member_casual,
    start_station_id,
    start_station_name,
    end_station_id,
    end_station_name,
    start_lat,
    start_lng,
    _source_month,
    _source_file,
    _ingested_at
from {{ ref('int_trips__checked') }}
where rejection_reason is not null
