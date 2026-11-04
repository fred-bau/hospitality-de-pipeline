{{ config(materialized='table') }}

-- One row per city: true city-level KPIs for the Tableau dashboard.
-- Medians and percentiles are computed here from the individual listings,
-- because they can't be rolled up from the neighbourhood summary.

with listings as (
    select * from {{ ref('stg_airbnb__listings') }}
),

cleaned as (
    select
        city,
        listing_id,
        host_id,
        room_type,
        is_host_superhost,
        license,
        calculated_host_listings_count,
        -- price arrives as text like '$1,234.00'; strip symbols and convert safely
        try_to_number(replace(replace(price_raw, '$', ''), ',', ''), 10, 2) as price_per_night,
        estimated_occupancy_l365d,
        estimated_revenue_l365d,
        number_of_reviews,
        review_scores_rating
    from listings
)

select
    city,

    -- Size of the market
    count(*)                                                        as listings_count,
    count(distinct host_id)                                         as hosts_count,

    -- Pricing: median plus the middle 50% range (25th to 75th percentile)
    round(median(price_per_night), 2)                               as median_price_per_night,
    round(percentile_cont(0.25) within group (order by price_per_night), 2) as p25_price_per_night,
    round(percentile_cont(0.75) within group (order by price_per_night), 2) as p75_price_per_night,
    round(avg(price_per_night), 2)                                  as avg_price_per_night,

    -- Occupancy & revenue (Inside Airbnb's own estimates)
    round(median(estimated_occupancy_l365d), 1)                     as median_occupied_nights_l365d,
    round(sum(estimated_revenue_l365d), 0)                          as total_estimated_revenue_l365d,

    -- Reviews & quality
    sum(number_of_reviews)                                          as total_reviews,
    round(avg(review_scores_rating), 2)                             as avg_review_rating,

    -- Market structure
    round(100 * avg(iff(is_host_superhost, 1, 0)), 1)               as pct_superhost_listings,
    round(100 * avg(iff(room_type = 'Entire home/apt', 1, 0)), 1)   as pct_entire_home,
    -- listings run by hosts with more than one listing (a sign of professional operators)
    round(100 * avg(iff(calculated_host_listings_count > 1, 1, 0)), 1) as pct_multi_listing_hosts,
    -- listings showing a registration or licence number (both cities regulate short-term rentals)
    round(100 * avg(iff(license is not null, 1, 0)), 1)             as pct_with_license

from cleaned
group by city
