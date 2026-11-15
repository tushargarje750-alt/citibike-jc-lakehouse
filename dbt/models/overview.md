{% docs __overview__ %}

# Citi Bike Jersey City & Hoboken — Lakehouse

Public Citi Bike trip data for Jersey City and Hoboken, plus daily weather,
modelled in three layers on Databricks (Delta Lake).

| Layer | Schema | What is in it |
|---|---|---|
| Bronze | `citibike_bronze` | Trips and weather exactly as published, loaded by notebooks with Auto Loader. dbt reads these as **sources**. |
| Silver | `citibike_silver` | Typed, checked, deduplicated trips (`fct_trips`), rejected rows with reasons (`trips_quarantine`), stations and daily weather. |
| Gold | `citibike_gold` | Six analytics tables: daily ridership, top stations, peak hours, member vs casual, weather impact, trip-duration stats. |

## How to read the lineage graph

Click the blue icon in the bottom-right corner. Green nodes are sources (bronze),
blue nodes are models. Data flows left to right: staging → intermediate → core → analytics.

## Data quality

- Every bronze row ends up in exactly one place: `fct_trips` or `trips_quarantine`.
  A test fails the build if the counts do not add up.
- Rejection rules and their thresholds are defined once, in `int_trips__checked`
  and the `vars` block of `dbt_project.yml`.
- Every gold table that counts trips is tested to add up to `fct_trips`.

Trip data: Citi Bike / Lyft (NYC Bike Share data licence). Weather data by Open-Meteo.com (CC BY 4.0).

{% enddocs %}
