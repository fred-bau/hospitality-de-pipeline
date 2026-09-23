{% snapshot scd_raw_listings %}

{{
    config(
      target_schema='snapshots',
      unique_key='id',
      strategy='check',
      check_cols=[
        'price',
        'minimum_nights',
        'maximum_nights',
        'instant_bookable',
        'host_is_superhost',
        'host_response_rate',
        'host_identity_verified',
        'host_listings_count',
        'property_type',
        'room_type',
        'accommodates',
        'bedrooms',
        'beds',
        'bathrooms',
        'review_scores_rating',
        'review_scores_cleanliness',
        'review_scores_value'
      ]
    )
}}

select * from {{ source('airbnb', 'raw_listings') }}

{% endsnapshot %}