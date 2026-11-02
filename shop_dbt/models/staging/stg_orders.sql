-- Clean orders.
-- The source sends (a) the original order row and (b) later status-update rows
-- for the same order_id. We keep the order details from (a) and the LATEST status.
with source as (
    select * from {{ source('raw', 'orders') }}
),

order_details as (
    select
        order_id,
        customer_id,
        product_id,
        cast(quantity as integer)                                  as quantity,
        cast(replace(amount, ',', '.') as decimal(10, 2))          as order_amount,  -- fix "12,50"
        cast(created_at as timestamp)                              as created_at,
        row_number() over (partition by order_id order by _loaded_at) as rn         -- drop duplicate exports
    from source
    where customer_id is not null and customer_id <> ''
),

latest_status as (
    select
        order_id,
        lower(trim(status))                as status,
        cast(updated_at as timestamp)      as status_updated_at,
        row_number() over (partition by order_id order by cast(updated_at as timestamp) desc) as rn
    from source
)

select
    d.order_id,
    d.customer_id,
    d.product_id,
    d.quantity,
    d.order_amount,
    d.created_at,
    cast(d.created_at as date)  as order_date,
    s.status,
    s.status_updated_at
from order_details d
join latest_status s on s.order_id = d.order_id and s.rn = 1
where d.rn = 1
