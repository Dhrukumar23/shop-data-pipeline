-- Clean payments: one row per payment, amounts as numbers
with ranked as (
    select
        *,
        row_number() over (partition by payment_id order by _loaded_at) as rn
    from {{ source('raw', 'payments') }}
)

select
    payment_id,
    order_id,
    cast(replace(amount, ',', '.') as decimal(10, 2)) as payment_amount,
    lower(method)                                     as payment_method,
    cast(paid_at as timestamp)                        as paid_at
from ranked
where rn = 1
