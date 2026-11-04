with reviews as (
    select * from {{ ref('stg_airbnb__reviews') }}
)

select
    listing_id,
    count(*) as total_reviews_count,
    min(review_date) as first_review_date,
    max(review_date) as last_review_date
from reviews
group by listing_id