"""
Semantic search over the reviews stored in Pinecone.

Run from the project root, with your question in quotes:
    python src/rag/search_reviews.py "noisy neighbours and thin walls"
"""
import os
import sys

from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

INDEX_NAME = "airbnb-reviews"
NAMESPACE = "reviews"
TOP_K = 5

question = " ".join(sys.argv[1:]) or "noisy neighbours and thin walls"

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(INDEX_NAME)

results = index.search(
    namespace=NAMESPACE,
    query={"inputs": {"text": question}, "top_k": TOP_K},
    fields=["review_text", "listing_id", "review_date"],
)

print(f'\nTop {TOP_K} reviews for: "{question}"\n')
for hit in results["result"]["hits"]:
    fields = hit["fields"]
    print(f"score {hit['_score']:.3f} | listing {fields['listing_id']} | {fields['review_date']}")
    print("   ", fields["review_text"][:300].replace("\n", " "))
    print()
