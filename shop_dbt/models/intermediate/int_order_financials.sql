-- Combine orders with payments and refunds (business rules live here, in one place)
--   FULL refund    = whole order amount
--   PARTIAL refund = 30 % of the order amount (shop policy for damaged goods)
--   A refund is capped at the amount actually paid
with payments as (
    select order_id, sum(payment_amount) as paid_amount
    from {{ ref('stg_payments') }}
    group by order_id
),

refunds as (
    select order_id, bool_or(refund_type = 'FULL') as has_full_refund
    from {{ ref('stg_refunds') }}
    group by order_id
)

select
    o.*,
    coalesce(p.paid_amount, 0)                                         as paid_amount,
    -- a refund can never be higher than what the customer actually paid
    least(
        case
            when r.has_full_refund      then o.order_amount
            when r.order_id is not null then round(o.order_amount * 0.30, 2)
            else 0
        end,
        coalesce(p.paid_amount, 0)
    )                                                                   as refund_amount
from {{ ref('stg_orders') }} o
left join payments p on p.order_id = o.order_id
left join refunds  r on r.order_id = o.order_id
