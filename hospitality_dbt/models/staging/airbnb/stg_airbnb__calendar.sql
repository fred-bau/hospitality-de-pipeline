with source as (
    {{ union_city_sources('calendar') }}
),

renamed as (
    select
        -- City & Foreign Key
        city,
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
