-- Business rule: an order can never have negative net revenue
select order_id, net_revenue
from {{ ref('fct_orders') }}
where net_revenue < 0
