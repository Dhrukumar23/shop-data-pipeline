"""
Runs the whole pipeline end to end, like a daily scheduled job:

    1. SOURCE     generate the shop system's daily export files (landing zone)
    2. EXTRACT +  load new daily batches into the DuckDB warehouse (raw layer),
       LOAD       incrementally - already loaded days are skipped
    3. TRANSFORM  dbt build: staging -> intermediate -> marts, plus data tests
    4. SERVE      export the mart tables to CSV for Power BI / Excel
    5. REPORT     print a short data-quality and KPI summary

Usage:
    python run_pipeline.py --days 30            # simulate 30 days in one go
    python run_pipeline.py --days 31            # next run: only day 31 is new

In a company, step 1 is the real source system and this script would be
scheduled daily (e.g. with Airflow, Azure Data Factory or a cron job).
"""
import argparse
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from generate_source_data import generate_day  # noqa: E402
import ingest  # noqa: E402

START = date(2026, 9, 1)


def step(title):
    print(f"\n=== {title} ===")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30, help="number of days since start to have in the landing zone")
    a = ap.parse_args()

    step("1. SOURCE: shop system exports daily files")
    for i in range(a.days):
        d = START + timedelta(days=i)
        if not (ROOT / "data" / "landing" / d.isoformat()).exists():
            generate_day(d, START)
    print(f"  landing zone holds {a.days} daily batches ({START} to {START + timedelta(days=a.days - 1)})")

    step("2. EXTRACT + LOAD: incremental load into warehouse (raw layer)")
    ingest.run()

    step("3. TRANSFORM: dbt build (models + tests)")
    dbt = subprocess.run(
        ["dbt", "--no-use-colors", "build", "--project-dir", "shop_dbt", "--profiles-dir", "shop_dbt"],
        cwd=ROOT, capture_output=True, text=True,
    )
    for line in dbt.stdout.splitlines():
        if any(k in line for k in (" OK created ", " PASS ", " ERROR ", " FAIL ", "Done. PASS")):
            print("  " + line[9:].strip())
    if dbt.returncode != 0:
        print(dbt.stdout[-3000:])
        sys.exit("dbt build failed - pipeline stopped (bad data is not published)")

    step("4. SERVE: export marts for Power BI")
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    con = duckdb.connect(str(ingest.WAREHOUSE), read_only=True)
    for t in ["fct_orders", "dim_customer", "dim_product", "mart_daily_revenue"]:
        con.execute(f"COPY marts.{t} TO '{(out / (t + '.csv')).as_posix()}' (HEADER)")
        print(f"  output/{t}.csv")

    step("5. REPORT: data quality and KPIs")
    raw_orders = con.execute("SELECT count(*) FROM raw.orders").fetchone()[0]
    clean_orders = con.execute("SELECT count(*) FROM marts.fct_orders").fetchone()[0]
    raw_cust = con.execute("SELECT count(*) FROM raw.customers").fetchone()[0]
    clean_cust = con.execute("SELECT count(*) FROM marts.dim_customer").fetchone()[0]
    variants = con.execute("SELECT count(DISTINCT country) FROM raw.customers").fetchone()[0]
    comma = con.execute("SELECT count(*) FROM raw.orders WHERE amount LIKE '%,%'").fetchone()[0]
    print(f"  orders:    {raw_orders:,} raw rows (incl. duplicates + status updates) -> {clean_orders:,} clean orders")
    print(f"  customers: {raw_cust:,} raw rows -> {clean_cust:,} unique customers")
    print(f"  country spellings standardised: {variants} variants -> 4 countries")
    print(f"  amounts fixed from comma format ('12,50'): {comma}")
    k = con.execute("""
        SELECT sum(gross_amount), sum(paid_amount), sum(refund_amount), sum(net_revenue),
               avg(CASE WHEN status='cancelled' THEN 1 ELSE 0 END)
        FROM marts.fct_orders""").fetchone()
    print(f"  gross EUR {k[0]:,.2f} | paid EUR {k[1]:,.2f} | refunds EUR {k[2]:,.2f} | net revenue EUR {k[3]:,.2f} | cancel rate {k[4]:.1%}")
    print("\n  net revenue by country:")
    for row in con.execute("""
        SELECT country, sum(net_revenue) AS net, sum(orders) AS orders
        FROM marts.mart_daily_revenue GROUP BY country ORDER BY net DESC""").fetchall():
        print(f"    {row[0]:<12} EUR {row[1]:>10,.2f}   ({row[2]} orders)")
    con.close()


if __name__ == "__main__":
    main()
