-- Clean products: latest price per product
with ranked as (
    select
        *,
        row_number() over (partition by product_id order by cast(updated_at as timestamp) desc) as rn
    from {{ source('raw', 'products') }}
)

select
    product_id,
    trim(product_name)                    as product_name,
    trim(category)                        as category,
    cast(list_price as decimal(10, 2))    as list_price,
    cast(updated_at as timestamp)         as updated_at
from ranked
where rn = 1
