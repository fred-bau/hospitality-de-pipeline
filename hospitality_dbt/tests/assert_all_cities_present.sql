-- Fails if any city in var('cities') has no listings in staging.
-- This is the test that would have caught Barcelona and Florence silently
-- missing from the warehouse. A dbt test fails when it returns rows.
{% for city in var('cities') %}
select '{{ city }}' as missing_city
where not exists (
    select 1
    from {{ ref('stg_airbnb__listings') }}
    where city = '{{ city }}'
)
{% if not loop.last %}union all{% endif %}
{% endfor %}
