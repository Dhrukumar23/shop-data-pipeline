"""
Step 2 - PIPELINE (Extract + Load): load landing files into the data warehouse.

- Warehouse: DuckDB (one file, works like Snowflake/BigQuery, but locally)
- Target:    schema "raw" (bronze layer) - data is stored exactly as received,
             plus metadata columns (_batch_date, _source_file, _loaded_at)
- Incremental: a load log remembers which daily batches are already loaded,
             so every run only loads NEW folders. Running it twice does not
             create duplicates (idempotent).

Transformations do NOT happen here - that is dbt's job (ELT pattern).
"""
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "data" / "landing"
WAREHOUSE = ROOT / "warehouse" / "shop.duckdb"
TABLES = ["customers", "products", "orders", "payments", "refunds"]


def connect():
    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.load_log (
            batch_date DATE, table_name VARCHAR, rows_loaded INTEGER, loaded_at TIMESTAMP)
    """)
    return con


def already_loaded(con) -> set:
    return {r[0].isoformat() for r in con.execute("SELECT DISTINCT batch_date FROM raw.load_log").fetchall()}


def load_batch(con, folder: Path) -> dict:
    batch = folder.name
    counts = {}
    for t in TABLES:
        f = folder / f"{t}.csv"
        if not f.exists():
            continue
        # read everything as text: raw layer keeps the data untouched
        select = f"""
            SELECT *, DATE '{batch}' AS _batch_date, '{f.name}' AS _source_file,
                   TIMESTAMP '{datetime.now():%Y-%m-%d %H:%M:%S}' AS _loaded_at
            FROM read_csv('{f.as_posix()}', header=true, all_varchar=true)
        """
        exists = con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='raw' AND table_name=?", [t]
        ).fetchone()[0]
        if exists:
            n = con.execute(f"INSERT INTO raw.{t} {select}").fetchone()[0]
        else:
            con.execute(f"CREATE TABLE raw.{t} AS {select}")
            n = con.execute(f"SELECT count(*) FROM raw.{t}").fetchone()[0]
        con.execute("INSERT INTO raw.load_log VALUES (?, ?, ?, now())", [batch, t, n])
        counts[t] = n
    return counts


def run() -> list:
    con = connect()
    done = already_loaded(con)
    new = sorted(p for p in LANDING.iterdir() if p.is_dir() and p.name not in done) if LANDING.exists() else []
    loaded = []
    for folder in new:
        counts = load_batch(con, folder)
        loaded.append((folder.name, counts))
        print(f"  loaded batch {folder.name}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    if not new:
        print("  nothing new to load (all batches already in the warehouse)")
    con.close()
    return loaded


if __name__ == "__main__":
    run()
