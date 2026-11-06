with listings as (
    select * from {{ ref('stg_airbnb__listings') }}
),

calendar as (
    select * from {{ ref('int_calendar_summarized') }}
),

reviews as (
    select * from {{ ref('int_reviews_summarized') }}
)

select
    -- Primary Keys & Dimensions
    l.listing_id,
    l.city,
    l.listing_name,
    l.room_type,
    l.neighborhood,
    -- All three cities (Paris, Barcelona, Florence) price in euros
    try_to_number(replace(replace(l.price_raw, '$', ''), ',', ''), 10, 2) as price_eur,
    l.minimum_nights,

    -- Calendar Summary Metrics
    coalesce(c.total_available_days, 0) as total_available_days,
    coalesce(c.total_calendar_days, 0) as total_calendar_days,

    -- Review Summary Metrics
    coalesce(r.total_reviews_count, 0) as total_reviews_count,
    r.first_review_date,
    r.last_review_date

from listings l
left join calendar c on l.listing_id = c.listing_id
left join reviews r on l.listing_id = r.listing_id
