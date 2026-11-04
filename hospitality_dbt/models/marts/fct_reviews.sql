with reviews as (
    select * from {{ ref('stg_airbnb__reviews') }}
)

select
    review_id,
    listing_id,
    city,
    reviewer_id,
    review_text,
    review_date
from reviews
