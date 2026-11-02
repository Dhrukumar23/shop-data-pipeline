"""
Step 1 - SOURCE: simulate the daily exports of an online shop system.

Every day the "shop system" drops CSV files into data/landing/<YYYY-MM-DD>/,
the way real ERP / shop / payment systems export data:

    customers.csv  - new and updated customers
    products.csv   - product master data (sent once, then only changes)
    orders.csv     - new orders AND status updates of older orders
    payments.csv   - payments from the payment provider
    refunds.csv    - refunds

The data is deliberately messy, like real source data:
    - duplicate rows (files re-sent by the source system)
    - the same order appearing again with a newer status (late-arriving updates)
    - inconsistent country spellings ("DE", "Germany", " germany ")
    - mixed upper/lower case e-mails
    - amounts sometimes with a comma as decimal separator ("12,50")

All data is simulated (portfolio project).
"""
import argparse
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "data" / "landing"

COUNTRIES = {
    "Germany": ["DE", "Germany", " germany ", "Deutschland"],
    "Italy": ["IT", "Italy", "italia"],
    "India": ["IN", "India", " india"],
    "Netherlands": ["NL", "Netherlands", "Holland"],
}
COUNTRY_WEIGHTS = [0.55, 0.15, 0.15, 0.15]
PRODUCTS = [
    ("P01", "Coffee Beans 1kg", "Coffee", 18.90),
    ("P02", "Espresso Beans 500g", "Coffee", 11.50),
    ("P03", "Green Tea 100g", "Tea", 6.90),
    ("P04", "Chai Spice Mix", "Spices", 5.40),
    ("P05", "Turmeric 250g", "Spices", 4.20),
    ("P06", "Milk Frother", "Equipment", 39.00),
    ("P07", "French Press", "Equipment", 29.50),
    ("P08", "Gift Box Deluxe", "Gifts", 54.00),
]


def write_csv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def fmt_amount(x: float, rng: random.Random) -> str:
    s = f"{x:.2f}"
    return s.replace(".", ",") if rng.random() < 0.08 else s  # messy decimals


def new_customers(day: date, start: date) -> int:
    return 25 if day == start else random.Random(day.toordinal() * 7).randint(3, 8)


def orders_per_day(day: date) -> int:
    return random.Random(day.toordinal() * 13).randint(40, 70)


def generate_day(day: date, start: date) -> Path:
    rng = random.Random(day.toordinal())
    folder = LANDING / day.isoformat()
    ts = lambda: datetime.combine(day, datetime.min.time()) + timedelta(seconds=rng.randint(0, 86399))

    # --- products: full list on day 1, afterwards only occasional price changes
    prod_rows = []
    for pid, name, cat, price in PRODUCTS:
        if day == start or rng.random() < 0.05:
            new_price = price if day == start else round(price * rng.uniform(0.95, 1.08), 2)
            prod_rows.append([pid, name, cat, f"{new_price:.2f}", ts().isoformat()])
    write_csv(folder / "products.csv", ["product_id", "product_name", "category", "list_price", "updated_at"], prod_rows)

    # --- customers: new ones each day + some profile updates
    day_idx = (day - start).days
    n_new = new_customers(day, start)
    first_id = 1000 + sum(new_customers(date.fromordinal(d), start) for d in range(start.toordinal(), day.toordinal()))
    cust_rows = []
    for i in range(n_new):
        cid = f"C{first_id + i}"
        country = rng.choices(list(COUNTRIES), COUNTRY_WEIGHTS)[0]
        email = f"customer{first_id + i}@example.com"
        email = email.upper() if rng.random() < 0.1 else email
        cust_rows.append([cid, f"Customer {first_id + i}", email, rng.choice(COUNTRIES[country]), ts().isoformat()])
    if cust_rows and rng.random() < 0.3:
        cust_rows.append(cust_rows[0])  # duplicate row re-sent by the source
    write_csv(folder / "customers.csv", ["customer_id", "customer_name", "email", "country", "updated_at"], cust_rows)

    known_customers = [f"C{c}" for c in range(1000, first_id + n_new)]

    # --- orders: new orders today + status updates for orders from previous days
    order_rows, pay_rows, refund_rows = [], [], []
    n_orders = orders_per_day(day)
    for i in range(n_orders):
        oid = f"O{day.strftime('%Y%m%d')}{i:03d}"
        cid = rng.choice(known_customers)
        pid, _, _, price = rng.choice(PRODUCTS)
        qty = rng.choice([1, 1, 1, 2, 2, 3])
        amount = round(price * qty, 2)
        created = ts()
        order_rows.append([oid, cid, pid, qty, fmt_amount(amount, rng), "placed", created.isoformat(), created.isoformat()])
        if rng.random() < 0.9:  # most orders are paid the same day
            pay_rows.append([f"PAY{oid}", oid, fmt_amount(amount, rng), rng.choice(["card", "paypal", "invoice"]), (created + timedelta(minutes=rng.randint(1, 120))).isoformat()])
        if rng.random() < 0.05:
            order_rows.append(order_rows[-1])  # duplicate export

    # late-arriving status updates for yesterday's orders
    if day_idx > 0:
        prev = day - timedelta(days=1)
        for i in range(orders_per_day(prev)):
            oid = f"O{prev.strftime('%Y%m%d')}{i:03d}"
            if rng.random() < 0.7:
                status = "shipped" if rng.random() < 0.93 else "cancelled"
                order_rows.append([oid, "", "", "", "", status, "", ts().isoformat()])
                if status == "cancelled" or rng.random() < 0.04:
                    refund_rows.append([f"REF{oid}", oid, "FULL" if status == "cancelled" else "PARTIAL", ts().isoformat()])

    write_csv(folder / "orders.csv", ["order_id", "customer_id", "product_id", "quantity", "amount", "status", "created_at", "updated_at"], order_rows)
    write_csv(folder / "payments.csv", ["payment_id", "order_id", "amount", "method", "paid_at"], pay_rows)
    write_csv(folder / "refunds.csv", ["refund_id", "order_id", "refund_type", "refunded_at"], refund_rows)
    return folder


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-09-01")
    ap.add_argument("--day", required=True, help="date to generate (YYYY-MM-DD)")
    a = ap.parse_args()
    print(generate_day(date.fromisoformat(a.day), date.fromisoformat(a.start)))
