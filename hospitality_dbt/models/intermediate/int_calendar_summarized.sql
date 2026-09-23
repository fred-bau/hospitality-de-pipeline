with calendar as (
    select * from {{ ref('stg_airbnb__calendar') }}
)

select
    listing_id,
    count(case when is_available = true then 1 end) as total_available_days,
    count(*) as total_calendar_days
from calendar
group by listing_id