{#
  Trip-length percentile in minutes, two decimals.
  Computed on the whole-second column and converted afterwards: taking an
  approximate percentile of the rounded decimal minutes column and rounding it
  again returned NULL when this was tested on Spark 4.0.
#}
{% macro percentile_minutes(fraction) -%}
    round(percentile_approx(duration_seconds, {{ fraction }}) / 60.0, 2)
{%- endmacro %}
