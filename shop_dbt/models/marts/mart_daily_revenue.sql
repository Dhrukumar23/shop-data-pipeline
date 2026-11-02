-- Daily KPIs per country - ready for a dashboard
select
    order_date,
    country,
    count(*)                                                    as orders,
    count(distinct customer_id)                                 as customers,
    sum(gross_amount)                                           as gross_amount,
    sum(refund_amount)                                          as refunds,
    sum(net_revenue)                                            as net_revenue,
    round(avg(case when status = 'cancelled' then 1 else 0 end), 3) as cancel_rate,
    round(avg(case when is_fully_paid then 0 else 1 end), 3)    as unpaid_rate
from {{ ref('fct_orders') }}
group by order_date, country
order by order_date, country
