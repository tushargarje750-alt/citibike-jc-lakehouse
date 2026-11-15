{#
  Prints the row counts for the silver layer. Run with:
      dbt run-operation silver_summary
#}
{% macro silver_summary() %}
    {% if not execute %}{{ return('') }}{% endif %}

    {% set totals = run_query(
        "select "
        ~ "(select count(*) from " ~ ref('stg_citibike__trips') ~ ") as staged, "
        ~ "(select count(*) from " ~ ref('fct_trips') ~ ") as accepted, "
        ~ "(select count(*) from " ~ ref('trips_quarantine') ~ ") as rejected, "
        ~ "(select count(*) from " ~ ref('dim_stations') ~ ") as stations, "
        ~ "(select count(*) from " ~ ref('dim_weather_daily') ~ ") as weather_days"
    ) %}
    {% set t = totals.rows[0] %}

    {% set trips = run_query(
        "select min(started_date) as first_day, max(started_date) as last_day, "
        ~ "sum(case when member_casual = 'member' then 1 else 0 end) as members, "
        ~ "sum(case when member_casual = 'casual' then 1 else 0 end) as casuals, "
        ~ "sum(case when not has_end_station then 1 else 0 end) as no_end_station, "
        ~ "sum(case when temperature_mean_c is null then 1 else 0 end) as no_weather, "
        ~ "round(percentile_approx(duration_minutes, 0.5), 1) as median_minutes "
        ~ "from " ~ ref('fct_trips')
    ) %}
    {% set f = trips.rows[0] %}

    {% set reasons = run_query(
        "select rejection_reason, count(*) as n from " ~ ref('trips_quarantine')
        ~ " group by rejection_reason order by n desc"
    ) %}
    {% set bikes = run_query(
        "select rideable_type, count(*) as n from " ~ ref('fct_trips')
        ~ " group by rideable_type order by n desc"
    ) %}
    {% set areas = run_query(
        "select area, count(*) as n from " ~ ref('dim_stations') ~ " group by area order by n desc"
    ) %}

    {% do log("===== SILVER SUMMARY (copy this block) =====", info=true) %}
    {% do log("staged bronze rows:        " ~ t['staged'], info=true) %}
    {% do log("accepted into fct_trips:   " ~ t['accepted'], info=true) %}
    {% do log("rejected (quarantine):     " ~ t['rejected'], info=true) %}
    {% do log("unaccounted rows:          " ~ (t['staged'] - t['accepted'] - t['rejected']), info=true) %}
    {% do log("trip days:                 " ~ f['first_day'] ~ " .. " ~ f['last_day'], info=true) %}
    {% do log("member / casual trips:     " ~ f['members'] ~ " / " ~ f['casuals'], info=true) %}
    {% do log("trips without end station: " ~ f['no_end_station'], info=true) %}
    {% do log("trips without weather:     " ~ f['no_weather'], info=true) %}
    {% do log("median trip minutes:       " ~ f['median_minutes'], info=true) %}
    {% do log("stations / weather days:   " ~ t['stations'] ~ " / " ~ t['weather_days'], info=true) %}
    {% do log("----- rejected rows by reason -----", info=true) %}
    {% for row in reasons.rows %}
        {% do log(row['rejection_reason'] ~ ": " ~ row['n'], info=true) %}
    {% endfor %}
    {% do log("----- accepted trips by bike type -----", info=true) %}
    {% for row in bikes.rows %}
        {% do log(row['rideable_type'] ~ ": " ~ row['n'], info=true) %}
    {% endfor %}
    {% do log("----- stations by area -----", info=true) %}
    {% for row in areas.rows %}
        {% do log(row['area'] ~ ": " ~ row['n'], info=true) %}
    {% endfor %}
    {% do log("============================================", info=true) %}
{% endmacro %}
