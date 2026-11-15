{#
  Custom generic test: fails for every row whose value is outside [min_value, max_value].
  Null values are ignored (use not_null for that). Either bound can be left out.

  Usage in a model's YAML:
      data_tests:
        - value_between:
            arguments:
              min_value: 60
              max_value: 86400
#}
{% test value_between(model, column_name, min_value=none, max_value=none) %}

select
    {{ column_name }} as value_out_of_range
from {{ model }}
where {{ column_name }} is not null
  and (
        {% if min_value is not none %}{{ column_name }} < {{ min_value }}{% else %}false{% endif %}
     or {% if max_value is not none %}{{ column_name }} > {{ max_value }}{% else %}false{% endif %}
  )

{% endtest %}
