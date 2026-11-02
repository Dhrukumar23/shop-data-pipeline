-- Clean refunds: one row per refund
with ranked as (
    select
        *,
        row_number() over (partition by refund_id order by _loaded_at) as rn
    from {{ source('raw', 'refunds') }}
)

select
    refund_id,
    order_id,
    upper(refund_type)              as refund_type,
    cast(refunded_at as timestamp)  as refunded_at
from ranked
where rn = 1
