-- Custom (singular) test: every gold table that counts trips must add up to
-- exactly the number of rows in fct_trips. Returns one row per table that does not.

with expected as (
    select count(*) as n from {{ ref('fct_trips') }}
),

totals as (
    select 'daily_ridership' as gold_table, sum(trips) as n from {{ ref('daily_ridership') }}
    union all
    select 'peak_hours', sum(trips) from {{ ref('peak_hours') }}
    union all
    select 'member_vs_casual', sum(trips) from {{ ref('member_vs_casual') }}
    union all
    select 'trip_duration_stats', sum(trips) from {{ ref('trip_duration_stats') }}
    union all
    select 'weather_impact', sum(trips) from {{ ref('weather_impact') }}
    union all
    select 'top_stations (starts)', sum(trips_started) + (
        select count(*) from {{ ref('fct_trips') }} where start_station_id is null
    ) from {{ ref('top_stations') }}
)

select
    totals.gold_table,
    totals.n                as gold_total,
    expected.n              as fct_trips_rows,
    totals.n - expected.n   as difference
from totals
cross join expected
where totals.n is null or totals.n <> expected.n
