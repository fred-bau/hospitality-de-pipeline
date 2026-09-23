with source as (
    select * from {{ source('airbnb', 'raw_reviews') }}
),

renamed as (
    select
        -- Primary & Foreign Keys
        id as review_id,
        listing_id,
        reviewer_id,

        -- Metadata
        reviewer_name,
        comments as review_text,

        -- Timestamps
        date::date as review_date

    from source
)

select * from renamed