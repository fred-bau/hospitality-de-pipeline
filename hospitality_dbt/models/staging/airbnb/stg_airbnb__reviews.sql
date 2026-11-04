with source as (
    {{ union_city_sources('reviews') }}
),

renamed as (
    select
        -- City
        city,

        -- Primary & Foreign Keys
        id as review_id,
        listing_id,
        reviewer_id,

        -- Content
        -- reviewer_name is deliberately left out: personal data that no
        -- downstream model needs (reviewer_id is enough to count reviewers)
        comments as review_text,

        -- Timestamps
        date::date as review_date

    from source
)

select * from renamed
