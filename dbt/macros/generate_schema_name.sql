{#
  dbt's default is to glue the target schema and the custom schema together
  (for example "citibike_citibike_silver"). This override uses the custom schema
  name as-is, with an optional prefix taken from the DBT_SCHEMA_PREFIX
  environment variable. CI sets that prefix to "ci_" so its tables never touch
  the real ones.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set prefix = env_var('DBT_SCHEMA_PREFIX', '') -%}
    {%- if custom_schema_name is none -%}
        {{ prefix }}{{ target.schema | trim }}
    {%- else -%}
        {{ prefix }}{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
