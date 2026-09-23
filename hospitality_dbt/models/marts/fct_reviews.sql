with reviews as (
    select * from {{ ref('stg_airbnb__reviews') }}
)

select
    review_id,
    listing_id,
    reviewer_id,
    reviewer_name,
    review_text,
    review_date
from reviews