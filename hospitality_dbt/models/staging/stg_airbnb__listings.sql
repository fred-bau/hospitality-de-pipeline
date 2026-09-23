with source as (
    select * from {{ source('airbnb', 'raw_listings') }}
),

renamed as (
    select
        -- Primary & Foreign Keys
        id as listing_id,
        host_id,
        scrape_id,

        -- URLs & Metadata
        listing_url,
        picture_url,
        source as listing_source,
        license,

        -- Listing Details
        name as listing_name,
        description as listing_description,
        neighborhood_overview,
        property_type,
        room_type,
        accommodates as accommodates_count,
        bathrooms as bathrooms_count,
        bathrooms_text,
        bedrooms as bedrooms_count,
        beds as beds_count,
        amenities as amenities_json,

        -- Location & Geography
        neighbourhood as neighborhood,
        neighbourhood_cleansed as neighborhood_cleansed,
        neighbourhood_group_cleansed as neighborhood_group_cleansed,
        latitude::number(10, 7) as latitude,
        longitude::number(10, 7) as longitude,

        -- Host Information & Metrics
        host_url,
        host_name,
        host_location,
        host_about,
        host_response_time,
        host_response_rate,
        host_acceptance_rate,
        host_is_superhost::boolean as is_host_superhost,
        host_thumbnail_url,
        host_picture_url,
        host_neighbourhood as host_neighborhood,
        host_listings_count,
        host_total_listings_count,
        host_verifications,
        host_has_profile_pic::boolean as has_host_profile_pic,
        host_identity_verified::boolean as is_host_identity_verified,
        host_profile_id,
        host_profile_url,
        hosts_time_as_user_years,
        hosts_time_as_user_months,
        hosts_time_as_host_years,
        hosts_time_as_host_months,

        -- Pricing & Quotes
        price as price_raw,
        price_quote_checkin_date,
        price_quote_checkout_date,
        price_quote_total_price,
        price_quote_price_per_night,
        price_quote_raw,

        -- Availability & Booking Rules
        minimum_nights,
        maximum_nights,
        minimum_minimum_nights,
        maximum_minimum_nights,
        minimum_maximum_nights,
        maximum_maximum_nights,
        minimum_nights_avg_ntm,
        maximum_nights_avg_ntm,
        calendar_updated,
        has_availability::boolean as has_availability,
        availability_30,
        availability_60,
        availability_90,
        availability_365,
        availability_eoy,
        instant_bookable::boolean as is_instant_bookable,

        -- Review Counts & Performance Metrics
        number_of_reviews,
        number_of_reviews_ltm,
        number_of_reviews_l30d,
        number_of_reviews_ly,
        reviews_per_month,
        estimated_occupancy_l365d,
        estimated_revenue_l365d,
        calculated_host_listings_count,
        calculated_host_listings_count_entire_homes,
        calculated_host_listings_count_private_rooms,
        calculated_host_listings_count_shared_rooms,

        -- Review Scores
        review_scores_rating,
        review_scores_accuracy,
        review_scores_cleanliness,
        review_scores_checkin,
        review_scores_communication,
        review_scores_location,
        review_scores_value,

        -- Dates & Timestamps
        last_scraped::timestamp_tz as last_scraped_at,
        calendar_last_scraped::date as calendar_last_scraped_at,
        host_since::date as host_since_date,
        first_review::date as first_review_date,
        last_review::date as last_review_date

    from source
)

select * from renamed