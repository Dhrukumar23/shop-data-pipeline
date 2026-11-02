-- Customer dimension (one row per customer)
select
    c.customer_id,
    c.customer_name,
    c.email,
    c.country,
    min(o.order_date)              as first_order_date,
    count(o.order_id)              as lifetime_orders
from {{ ref('stg_customers') }} c
left join {{ ref('stg_orders') }} o on o.customer_id = c.customer_id
group by all
