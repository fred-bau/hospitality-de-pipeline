with source as (
    select * from {{ source('airbnb', 'raw_calendar') }}
),

renamed as (
    select
        -- Foreign Key
        listing_id,

        -- Timestamps
        date::date as calendar_date,

        -- Status & Attributes
        available::boolean as is_available,
        minimum_nights,
        maximum_nights

    from source
)

select * from renamed