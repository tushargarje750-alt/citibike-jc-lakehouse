-- Custom (singular) test: nothing may be lost between bronze and silver.
-- Every staged bronze row must land in exactly one place:
--   fct_trips (accepted) or trips_quarantine (rejected, with a reason).
-- The test returns a row, and therefore fails, when the counts do not add up.

with staged as (
    select count(*) as n from {{ ref('stg_citibike__trips') }}
),

accepted as (
    select count(*) as n from {{ ref('fct_trips') }}
),

rejected as (
    select count(*) as n from {{ ref('trips_quarantine') }}
)

select
    staged.n                              as staged_rows,
    accepted.n                            as accepted_rows,
    rejected.n                            as rejected_rows,
    staged.n - accepted.n - rejected.n    as unaccounted_rows
from staged
cross join accepted
cross join rejected
where staged.n <> accepted.n + rejected.n
