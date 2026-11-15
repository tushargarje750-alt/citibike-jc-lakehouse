-- Custom (singular) test, warning only: a sudden jump in rejected rows usually
-- means the source changed, not that riders did. Warns when the rejected share
-- of all staged rows is above the max_quarantine_share variable (default 5%).

{{ config(severity='warn') }}

with counts as (
    select
        (select count(*) from {{ ref('trips_quarantine') }})      as rejected_rows,
        (select count(*) from {{ ref('stg_citibike__trips') }})   as staged_rows
)

select
    rejected_rows,
    staged_rows,
    round(rejected_rows / nullif(staged_rows, 0), 4) as rejected_share
from counts
where rejected_rows / nullif(staged_rows, 0) > {{ var('max_quarantine_share') }}
