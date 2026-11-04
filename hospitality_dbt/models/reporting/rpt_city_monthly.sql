{{ config(materialized='table') }}

-- One row per city per month, combining two time series:
--
--   * Availability (from the calendar): FORWARD-LOOKING. Inside Airbnb's calendar
--     covers the ~12 months after the scrape date. "Not available" means booked OR
--     blocked by the host, so it's an upper bound on occupancy, not a booking count.
--
--   * Review activity (from reviews): BACKWARD-LOOKING, going back years. Reviews
--     are a common proxy for demand (guests usually review after a stay).
--
-- The two series cover different months, so each row usually has values in only
-- one of the two groups of columns; the other group is null.

with calendar_monthly as (
    select
        city,
        date_trunc('month', calendar_date)::date                    as month,
        count(distinct listing_id)                                  as listings_in_calendar,
        count(*)                                                    as listing_days,
        sum(iff(is_available, 1, 0))                                as available_days
    from {{ ref('fct_calendar') }}
    group by city, date_trunc('month', calendar_date)::date
),

reviews_monthly as (
    select
        city,
        date_trunc('month', review_date)::date                      as month,
        -- fct_reviews has one row per review PER LISTING (hotels share reviews
        -- across their room listings), so count each review only once
        count(distinct review_id)                                   as reviews_count,
        count(distinct listing_id)                                  as listings_reviewed
    from {{ ref('fct_reviews') }}
    group by city, date_trunc('month', review_date)::date
)

select
    coalesce(c.city, r.city)                                        as city,
    coalesce(c.month, r.month)                                      as month,

    -- Availability (future months)
    c.listings_in_calendar,
    c.listing_days,
    c.available_days,
    round(100 * c.available_days / nullif(c.listing_days, 0), 1)    as availability_rate_pct,

    -- Review activity (past months)
    r.reviews_count,
    r.listings_reviewed

from calendar_monthly c
full outer join reviews_monthly r
    on c.city = r.city
   and c.month = r.month
