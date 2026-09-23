with calendar as (
    select * from {{ ref('stg_airbnb__calendar') }}
)

select
    listing_id,
    calendar_date,
    is_available,
    minimum_nights,
    maximum_nights
from calendar