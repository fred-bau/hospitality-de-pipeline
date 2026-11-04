"""
Load a sample of guest reviews from Snowflake into Pinecone, for all cities.

- Logs in to Snowflake with the key pair (password logins are blocked by MFA).
- Samples the same number of reviews per city, so no city dominates searches.
- Stores `city` as metadata, so searches can be filtered by city.
- Full refresh: empties the namespace first, then loads the new sample.

Pinecone embeds the text itself (integrated embedding), so no separate
embedding model or API key is needed for this step.

Run from the project root:
    python src/rag/load_reviews_to_pinecone.py
"""
import os
import time

import snowflake.connector
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

# ---- Settings ----
INDEX_NAME = "airbnb-reviews"
NAMESPACE = "reviews"
REVIEWS_PER_CITY = 1500     # 3 cities x 1,500 = 4,500 reviews; fine for the free plan
BATCH_SIZE = 96             # max records per upsert for Pinecone-hosted models
SOURCE_TABLE = "TRANSFORM.FCT_REVIEWS"
MIN_TEXT_LENGTH = 30        # skip very short reviews like "Great!"
MAX_TEXT_LENGTH = 2000      # truncate very long reviews
RANDOM_SEED = 42            # same seed = same sample on every run (reproducible)


def fetch_reviews():
    """Pull an equal-sized random sample of reviews per city from Snowflake."""
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )
    query = f"""
        with one_row_per_review as (
            -- fct_reviews has one row per review per listing (hotels share reviews
            -- across their room listings); keep each review only once
            select review_id, listing_id, city, review_date, review_text
            from {SOURCE_TABLE}
            where review_text is not null
              and length(review_text) >= {MIN_TEXT_LENGTH}
            qualify row_number() over (partition by review_id order by listing_id) = 1
        )
        select review_id, listing_id, city, review_date, review_text
        from one_row_per_review
        -- the same number of random reviews from each city
        qualify row_number() over (partition by city order by random({RANDOM_SEED}))
                <= {REVIEWS_PER_CITY}
    """
    try:
        cur = conn.cursor()
        cur.execute(query)
        return cur.fetchall()
    finally:
        conn.close()


def to_records(rows):
    """Turn Snowflake rows into Pinecone records (metadata can't be null)."""
    records = []
    for review_id, listing_id, city, review_date, text in rows:
        clean_text = text.replace("<br/>", " ").replace("\r", " ").strip()
        records.append({
            "_id": str(review_id),
            "review_text": clean_text[:MAX_TEXT_LENGTH],
            "listing_id": str(listing_id),
            "city": city,
            "review_date": str(review_date),
        })
    return records


def main():
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

    if not pc.has_index(INDEX_NAME):
        print(f"Creating index '{INDEX_NAME}'...")
        pc.create_index_for_model(
            name=INDEX_NAME,
            cloud="aws",
            region="us-east-1",
            embed={
                "model": "llama-text-embed-v2",
                "field_map": {"text": "review_text"},
            },
        )

    index = pc.Index(INDEX_NAME)

    # Full refresh: remove the old records first (the earlier Paris-only sample
    # has no `city` metadata and would be invisible to city-filtered searches)
    try:
        index.delete(delete_all=True, namespace=NAMESPACE)
        print(f"Emptied namespace '{NAMESPACE}'.")
    except Exception as e:  # the namespace doesn't exist yet on a first run
        print(f"Namespace '{NAMESPACE}' not emptied (probably doesn't exist yet): {e}")

    print("Fetching reviews from Snowflake...")
    records = to_records(fetch_reviews())
    per_city = {}
    for r in records:
        per_city[r["city"]] = per_city.get(r["city"], 0) + 1
    print(f"Fetched {len(records)} reviews: {per_city}")

    print(f"Uploading in batches of {BATCH_SIZE}...")
    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start:start + BATCH_SIZE]
        for attempt in range(5):
            try:
                index.upsert_records(NAMESPACE, batch)
                break
            except Exception as e:  # usually a rate limit on the free plan
                wait = 20 * (attempt + 1)
                print(f"  batch at {start} failed ({e}); retrying in {wait}s")
                time.sleep(wait)
        else:
            raise RuntimeError(f"Batch starting at {start} failed after 5 attempts")
        print(f"  uploaded {min(start + BATCH_SIZE, len(records))}/{len(records)}")
        time.sleep(1)  # stay under the free plan's embedding rate limit

    time.sleep(10)  # Pinecone is eventually consistent; give the stats a moment
    print("Done. Index stats:", index.describe_index_stats())


if __name__ == "__main__":
    main()
