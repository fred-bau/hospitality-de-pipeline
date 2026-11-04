{{ config(materialized='table') }}

-- Reporting model for the Tableau dashboard: one row per city and neighbourhood.
-- Aggregation happens here in the warehouse, so the BI tool only visualises.

with listings as (
    select * from {{ ref('stg_airbnb__listings') }}
),

cleaned as (
    select
        listing_id,
        city,
        neighborhood_cleansed,
        room_type,
        is_host_superhost,
        -- price arrives as text like '$1,234.00'; strip symbols and convert safely
        try_to_number(replace(replace(price_raw, '$', ''), ',', ''), 10, 2) as price_per_night,
        availability_365,
        estimated_occupancy_l365d,
        estimated_revenue_l365d,
        number_of_reviews,
        review_scores_rating
    from listings
    where neighborhood_cleansed is not null
)

select
    city,
    neighborhood_cleansed                                         as neighborhood,
    count(*)                                                      as listings_count,

    -- Pricing (median is robust to extreme outlier prices)
    round(median(price_per_night), 2)                             as median_price_per_night,
    round(avg(price_per_night), 2)                                as avg_price_per_night,

    -- Occupancy & revenue (Inside Airbnb's own estimates)
    round(avg(estimated_occupancy_l365d), 1)                      as avg_occupied_nights_l365d,
    round(avg(availability_365), 1)                               as avg_available_nights_365,
    round(sum(estimated_revenue_l365d), 0)                        as total_estimated_revenue_l365d,

    -- Reviews & quality
    sum(number_of_reviews)                                        as total_reviews,
    round(avg(review_scores_rating), 2)                           as avg_review_rating,

    -- Mix of listings
    round(100 * avg(iff(is_host_superhost, 1, 0)), 1)             as pct_superhost_listings,
    round(100 * avg(iff(room_type = 'Entire home/apt', 1, 0)), 1) as pct_entire_home

from cleaned
group by city, neighborhood_cleansed
