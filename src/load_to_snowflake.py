"""
Load the raw Inside Airbnb files for each city from S3 into Snowflake.

Reads:   s3://<bucket>/raw/<city>/<type>_<city>.csv.gz
Writes:  <database>.RAW.raw_<type>_<city>      e.g. RAW.raw_listings_paris

Each table is emptied and fully reloaded on every run (full refresh), so
rerunning the script never creates duplicates. The script fails loudly if a
file is missing in S3, if a file fails to load, or if a table ends up empty.

Run from the project root:
    python src/load_to_snowflake.py
"""
import os

import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

# ---- Settings ----
CITIES = ["paris", "barcelona", "florence"]
FILE_TYPES = ["listings", "reviews", "calendar"]
S3_PREFIX = "raw"
SNOWFLAKE_SCHEMA = "RAW"

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")


def get_snowflake_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )


def load_one(cursor, city, file_type):
    """Full refresh of one table from one S3 file. Returns the number of rows loaded."""
    table = f"{SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.raw_{file_type}_{city}"
    s3_path = f"s3://{S3_BUCKET_NAME}/{S3_PREFIX}/{city}/{file_type}_{city}.csv.gz"
    print(f"  {s3_path} -> {table}")

    # 1. Empty the table so a rerun replaces the data instead of appending to it
    cursor.execute(f"truncate table {table}")

    # 2. Copy the file in. ON_ERROR = ABORT_STATEMENT: any bad row fails the load.
    cursor.execute(f"""
        copy into {table}
        from '{s3_path}'
        credentials = (
            aws_key_id = '{AWS_ACCESS_KEY_ID}'
            aws_secret_key = '{AWS_SECRET_ACCESS_KEY}'
        )
        file_format = (
            type = 'CSV'
            field_optionally_enclosed_by = '"'
            skip_header = 1
            compression = 'GZIP'
            null_if = ('', 'NULL', 'null')
            empty_field_as_null = true
            escape_unenclosed_field = none
        )
        on_error = 'ABORT_STATEMENT'
        force = true
    """)

    # 3. Check what COPY reported. When no file is found, Snowflake returns a single
    #    message ("Copy executed with 0 files processed") instead of per-file results.
    columns = [col[0].lower() for col in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    if "status" not in columns or not results:
        raise RuntimeError(f"No file was loaded from {s3_path}: {results}")

    rows_loaded = 0
    for r in results:
        if r["status"] != "LOADED":
            raise RuntimeError(f"Loading {r['file']} failed: {r.get('first_error')}")
        rows_loaded += r["rows_loaded"]

    # 4. Reconcile: the table must contain exactly the rows COPY says it loaded
    cursor.execute(f"select count(*) from {table}")
    table_rows = cursor.fetchone()[0]
    if table_rows == 0 or table_rows != rows_loaded:
        raise RuntimeError(
            f"{table}: COPY reported {rows_loaded} rows but the table has {table_rows}"
        )

    print(f"    loaded {rows_loaded:,} rows")
    return rows_loaded


def main():
    for name in ["S3_BUCKET_NAME", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "SNOWFLAKE_DATABASE"]:
        if not os.getenv(name):
            raise RuntimeError(f"{name} is not set (check your .env)")

    print("Starting Snowflake load...")
    summary = {}
    conn = get_snowflake_connection()
    try:
        cursor = conn.cursor()
        for city in CITIES:
            print(f"\n{city}:")
            for file_type in FILE_TYPES:
                summary[(city, file_type)] = load_one(cursor, city, file_type)
        cursor.close()
    finally:
        conn.close()

    print("\nSummary (rows loaded):")
    print(f"  {'city':<12}{'listings':>12}{'reviews':>14}{'calendar':>14}")
    for city in CITIES:
        counts = [summary[(city, t)] for t in FILE_TYPES]
        print(f"  {city:<12}" + "".join(f"{c:>14,}" if i else f"{c:>12,}" for i, c in enumerate(counts)))
    print("\nAll 9 tables loaded and verified.")


if __name__ == "__main__":
    main()