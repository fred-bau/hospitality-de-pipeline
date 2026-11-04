-- Fails if the city summary's listing counts don't add up to the number of
-- listings in staging. A reconciliation test: no listing lost or double counted
-- on the way from staging to the report. Returns a row per mismatching city.
with report as (
    select city, listings_count
    from {{ ref('rpt_city_summary') }}
),

source as (
    select city, count(*) as listings_count
    from {{ ref('stg_airbnb__listings') }}
    group by city
)

select
    coalesce(s.city, r.city) as city,
    s.listings_count         as listings_in_staging,
    r.listings_count         as listings_in_report
from source s
full outer join report r on s.city = r.city
where s.listings_count is distinct from r.listings_count
