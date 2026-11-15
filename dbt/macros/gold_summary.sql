{#
  Prints headline numbers from the gold layer. Run with:
      dbt run-operation gold_summary
#}
{% macro gold_summary() %}
    {% if not execute %}{{ return('') }}{% endif %}

    {% set sizes = run_query(
        "select "
        ~ "(select count(*) from " ~ ref('daily_ridership') ~ ") as daily_ridership, "
        ~ "(select count(*) from " ~ ref('top_stations') ~ ") as top_stations, "
        ~ "(select count(*) from " ~ ref('peak_hours') ~ ") as peak_hours, "
        ~ "(select count(*) from " ~ ref('member_vs_casual') ~ ") as member_vs_casual, "
        ~ "(select count(*) from " ~ ref('weather_impact') ~ ") as weather_impact, "
        ~ "(select count(*) from " ~ ref('trip_duration_stats') ~ ") as trip_duration_stats"
    ).rows[0] %}

    {% set daily = run_query(
        "select sum(trips) as trips, round(avg(trips), 0) as avg_per_day, "
        ~ "max_by(ride_date, trips) as busiest_day, max(trips) as busiest_trips, "
        ~ "round(sum(member_trips) / sum(trips), 4) as member_share, "
        ~ "round(sum(electric_trips) / sum(trips), 4) as electric_share "
        ~ "from " ~ ref('daily_ridership')
    ).rows[0] %}

    {% set yearly = run_query(
        "select ride_year, sum(trips) as trips, count(*) as days, round(avg(trips), 0) as avg_per_day "
        ~ "from " ~ ref('daily_ridership') ~ " group by ride_year order by ride_year"
    ) %}

    {% set stations = run_query(
        "select start_rank, station_name, area, trips_started from " ~ ref('top_stations')
        ~ " order by start_rank, station_name limit 5"
    ) %}

    {% set areas = run_query(
        "select area, count(*) as stations, sum(trips_started) as trips_started, sum(trips_ended) as trips_ended "
        ~ "from " ~ ref('top_stations') ~ " group by area order by trips_started desc"
    ) %}

    {% set peaks = run_query(
        "select day_type, started_hour, trips from ("
        ~ "select day_type, started_hour, trips, row_number() over (partition by day_type order by trips desc) as rn from ("
        ~ "select case when is_weekend then 'weekend' else 'weekday' end as day_type, started_hour, sum(trips) as trips "
        ~ "from " ~ ref('peak_hours') ~ " group by 1, 2) hourly) ranked where rn = 1 order by day_type"
    ) %}

    {% set riders = run_query(
        "select member_casual, sum(trips) as trips, "
        ~ "round(sum(median_duration_minutes * trips) / sum(trips), 1) as typical_median_minutes, "
        ~ "round(sum(weekend_share * trips) / sum(trips), 3) as weekend_share "
        ~ "from " ~ ref('member_vs_casual') ~ " group by member_casual order by member_casual"
    ) %}

    {% set weather = run_query(
        "select is_wet_day, sum(days) as days, "
        ~ "round(sum(avg_ridership_index * days) / sum(days), 3) as ridership_index "
        ~ "from " ~ ref('weather_impact') ~ " group by is_wet_day order by is_wet_day"
    ) %}

    {% set bands = run_query(
        "select temperature_band, sum(days) as days, "
        ~ "round(sum(avg_ridership_index * days) / sum(days), 3) as ridership_index "
        ~ "from " ~ ref('weather_impact') ~ " where not is_wet_day group by temperature_band "
        ~ "order by case temperature_band when 'freezing' then 1 when 'cold' then 2 when 'mild' then 3 when 'warm' then 4 else 5 end"
    ) %}

    {% do log("===== GOLD SUMMARY (copy this block) =====", info=true) %}
    {% do log("rows: daily_ridership " ~ sizes['daily_ridership'] ~ ", top_stations " ~ sizes['top_stations']
              ~ ", peak_hours " ~ sizes['peak_hours'] ~ ", member_vs_casual " ~ sizes['member_vs_casual']
              ~ ", weather_impact " ~ sizes['weather_impact'] ~ ", trip_duration_stats " ~ sizes['trip_duration_stats'], info=true) %}
    {% do log("total trips: " ~ daily['trips'] ~ " | average per day: " ~ daily['avg_per_day'], info=true) %}
    {% do log("busiest day: " ~ daily['busiest_day'] ~ " with " ~ daily['busiest_trips'] ~ " trips", info=true) %}
    {% do log("member share: " ~ daily['member_share'] ~ " | electric share: " ~ daily['electric_share'], info=true) %}
    {% do log("----- trips by year -----", info=true) %}
    {% for row in yearly.rows %}
        {% do log(row['ride_year'] ~ ": " ~ row['trips'] ~ " trips over " ~ row['days'] ~ " days, " ~ row['avg_per_day'] ~ " per day", info=true) %}
    {% endfor %}
    {% do log("----- top 5 start stations -----", info=true) %}
    {% for row in stations.rows %}
        {% do log("#" ~ row['start_rank'] ~ " " ~ row['station_name'] ~ " (" ~ row['area'] ~ "): " ~ row['trips_started'], info=true) %}
    {% endfor %}
    {% do log("----- stations and trips by area -----", info=true) %}
    {% for row in areas.rows %}
        {% do log(row['area'] ~ ": " ~ row['stations'] ~ " stations, " ~ row['trips_started'] ~ " trips started, " ~ row['trips_ended'] ~ " ended", info=true) %}
    {% endfor %}
    {% do log("----- busiest hour -----", info=true) %}
    {% for row in peaks.rows %}
        {% do log(row['day_type'] ~ ": " ~ row['started_hour'] ~ ":00 (" ~ row['trips'] ~ " trips)", info=true) %}
    {% endfor %}
    {% do log("----- members vs casual riders -----", info=true) %}
    {% for row in riders.rows %}
        {% do log(row['member_casual'] ~ ": " ~ row['trips'] ~ " trips, typical median " ~ row['typical_median_minutes'] ~ " min, weekend share " ~ row['weekend_share'], info=true) %}
    {% endfor %}
    {% do log("----- weather (ridership index: 1.0 = a normal day for that month) -----", info=true) %}
    {% for row in weather.rows %}
        {% do log(("wet days" if row['is_wet_day'] else "dry days") ~ ": " ~ row['days'] ~ " days, index " ~ row['ridership_index'], info=true) %}
    {% endfor %}
    {% for row in bands.rows %}
        {% do log("dry + " ~ row['temperature_band'] ~ ": " ~ row['days'] ~ " days, index " ~ row['ridership_index'], info=true) %}
    {% endfor %}
    {% do log("==========================================", info=true) %}
{% endmacro %}
