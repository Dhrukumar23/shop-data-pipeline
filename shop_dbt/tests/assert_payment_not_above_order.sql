-- Data quality: a payment should never be higher than the order amount
select order_id, gross_amount, paid_amount
from {{ ref('fct_orders') }}
where paid_amount > gross_amount + 0.01
