-- Clean customers: keep the latest version per customer, standardise country and e-mail
with source as (
    select * from {{ source('raw', 'customers') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by customer_id
            order by cast(updated_at as timestamp) desc, _loaded_at desc
        ) as rn
    from source
)

select
    customer_id,
    trim(customer_name)                    as customer_name,
    lower(trim(email))                     as email,
    case
        when lower(trim(country)) in ('de', 'germany', 'deutschland') then 'Germany'
        when lower(trim(country)) in ('it', 'italy', 'italia')        then 'Italy'
        when lower(trim(country)) in ('in', 'india')                  then 'India'
        when lower(trim(country)) in ('nl', 'netherlands', 'holland') then 'Netherlands'
        else 'Unknown'
    end                                    as country,
    cast(updated_at as timestamp)          as updated_at
from ranked
where rn = 1
