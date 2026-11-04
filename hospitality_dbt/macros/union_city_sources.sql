{#
    Stacks the per-city raw tables of one type into a single result,
    adding a `city` column that says which city each row came from.

    Usage:  {{ union_city_sources('listings') }}
    reads:  raw_listings_paris, raw_listings_barcelona, raw_listings_florence
            (one per city in var('cities'))

    `union all` matches columns by position, which is safe here because all
    per-city tables were created with the same structure (create table ... like).
#}
{% macro union_city_sources(table_type) %}
    {%- for city in var('cities') %}
    select
        '{{ city }}' as city,
        *
    from {{ source('airbnb', 'raw_' ~ table_type ~ '_' ~ city) }}
    {%- if not loop.last %}
    union all
    {%- endif %}
    {%- endfor %}
{% endmacro %}
