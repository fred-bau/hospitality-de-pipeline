"""
Semantic search over the reviews stored in Pinecone, optionally for one city.

Run from the project root:
    python src/rag/search_reviews.py "noisy neighbours and thin walls"
    python src/rag/search_reviews.py "noisy neighbours and thin walls" --city florence
"""
import argparse
import os

from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

INDEX_NAME = "airbnb-reviews"
NAMESPACE = "reviews"
CITIES = ["paris", "barcelona", "florence"]

parser = argparse.ArgumentParser(description="Semantic search over guest reviews")
parser.add_argument("question", nargs="*", help="what to search for")
parser.add_argument("--city", choices=CITIES, help="only search reviews from this city")
parser.add_argument("--top-k", type=int, default=5, help="number of results (default 5)")
args = parser.parse_args()

question = " ".join(args.question) or "noisy neighbours and thin walls"

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(INDEX_NAME)

query = {"inputs": {"text": question}, "top_k": args.top_k}
if args.city:
    query["filter"] = {"city": {"$eq": args.city}}

results = index.search(
    namespace=NAMESPACE,
    query=query,
    fields=["review_text", "listing_id", "city", "review_date"],
)

scope = args.city or "all cities"
print(f'\nTop {args.top_k} reviews for: "{question}" ({scope})\n')
for hit in results["result"]["hits"]:
    fields = hit["fields"]
    print(
        f"score {hit['_score']:.3f} | {fields['city']} | "
        f"listing {fields['listing_id']} | {fields['review_date']}"
    )
    print("   ", fields["review_text"][:300].replace("\n", " "))
    print()
