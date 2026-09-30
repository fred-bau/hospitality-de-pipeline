"""
Load a sample of Airbnb reviews from Snowflake into Pinecone.

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

# ---- Settings: adjust these to match your project ----
INDEX_NAME = "airbnb-reviews"
NAMESPACE = "reviews"
SAMPLE_SIZE = 3000          # reviews to embed; keep small on the free plan
BATCH_SIZE = 96             # max records per upsert for Pinecone-hosted models
SOURCE_TABLE = "TRANSFORM.FCT_REVIEWS"
ID_COLUMN = "REVIEW_ID"
LISTING_COLUMN = "LISTING_ID"
DATE_COLUMN = "REVIEW_DATE"
TEXT_COLUMN = "REVIEW_TEXT"    # the column holding the review text
MIN_TEXT_LENGTH = 30        # skip very short reviews like "Great!"
MAX_TEXT_LENGTH = 2000      # truncate very long reviews


def fetch_reviews():
    """Pull a random sample of non-trivial reviews from Snowflake."""
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )
    query = f"""
        select {ID_COLUMN}, {LISTING_COLUMN}, {DATE_COLUMN}, {TEXT_COLUMN}
        from {SOURCE_TABLE}
        where {TEXT_COLUMN} is not null
          and length({TEXT_COLUMN}) >= {MIN_TEXT_LENGTH}
        order by random()
        limit {SAMPLE_SIZE}
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
    for review_id, listing_id, review_date, text in rows:
        clean_text = text.replace("<br/>", " ").replace("\r", " ").strip()
        records.append({
            "_id": str(review_id),
            "review_text": clean_text[:MAX_TEXT_LENGTH],
            "listing_id": str(listing_id),
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

    print("Fetching reviews from Snowflake...")
    records = to_records(fetch_reviews())
    print(f"Fetched {len(records)} reviews. Uploading in batches of {BATCH_SIZE}...")

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

    print("Done. Index stats:", index.describe_index_stats())


if __name__ == "__main__":
    main()
