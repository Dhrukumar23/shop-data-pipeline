-- Order fact table (one row per order) - the main table for Power BI
select
    f.order_id,
    f.order_date,
    f.customer_id,
    f.product_id,
    c.country,
    p.category,
    f.status,
    f.quantity,
    f.order_amount                          as gross_amount,
    f.paid_amount,
    f.refund_amount,
    f.paid_amount - f.refund_amount         as net_revenue,
    f.paid_amount >= f.order_amount         as is_fully_paid
from {{ ref('int_order_financials') }} f
left join {{ ref('dim_customer') }} c on c.customer_id = f.customer_id
left join {{ ref('dim_product') }}  p on p.product_id  = f.product_id
