{#
  Custom generic test: fails when two rows share the same values in all the listed
  columns. Use it on a model whose key is more than one column.

  Usage in a model's YAML (model level, not under a column):
      data_tests:
        - unique_combination:
            arguments:
              columns: [ride_month, member_casual]
#}
{% test unique_combination(model, columns) %}

select
    {{ columns | join(', ') }},
    count(*) as rows_with_this_key
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1

{% endtest %}
