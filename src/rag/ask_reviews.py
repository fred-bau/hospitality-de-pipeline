"""
Ask questions about guest reviews (RAG: retrieval-augmented generation),
optionally for one city.

  1. Retrieve the most relevant reviews from Pinecone (filtered by city if given)
  2. Pass them to Claude through a LangChain chain
  3. Claude writes an answer based only on those reviews

Run from the project root:
    python src/rag/ask_reviews.py "What do guests complain about most?"
    python src/rag/ask_reviews.py "What do guests complain about most?" --city barcelona
"""
import argparse
import os

from typing import Optional

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from pinecone import Pinecone

load_dotenv()  # loads PINECONE_API_KEY and ANTHROPIC_API_KEY from .env

# ---- Settings ----
INDEX_NAME = "airbnb-reviews"
NAMESPACE = "reviews"
CITIES = ["paris", "barcelona", "florence"]
TOP_K = 10                               # how many reviews Claude gets to read
MODEL = "claude-haiku-4-5-20251001"      # fast and cheap; "claude-sonnet-5-5" for higher quality

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(INDEX_NAME)


def retrieve_reviews(question: str, city: Optional[str]) -> str:
    """Step 1: semantic search in Pinecone, formatted as numbered text for the prompt."""
    query = {"inputs": {"text": question}, "top_k": TOP_K}
    if city:
        query["filter"] = {"city": {"$eq": city}}

    results = index.search(
        namespace=NAMESPACE,
        query=query,
        fields=["review_text", "listing_id", "city", "review_date"],
    )
    hits = results["result"]["hits"]
    if not hits:
        return "No relevant reviews found."

    blocks = []
    for i, hit in enumerate(hits, start=1):
        f = hit["fields"]
        blocks.append(
            f"[Review {i}] {f['city'].title()}, listing {f['listing_id']}, "
            f"{f['review_date']}:\n{f['review_text']}"
        )
    return "\n\n".join(blocks)


# Step 2: the prompt that combines the retrieved reviews with the question
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a hospitality analyst. Answer the user's question using only the "
        "guest reviews provided. Each review is labelled with its city. Reviews may "
        "be in any language; always answer in English. Cite the reviews you rely on "
        "by number, e.g. [Review 3]. If the reviews don't contain enough information "
        "to answer, say so instead of guessing. Answer in plain text without markdown "
        "formatting, in under 200 words.",
    ),
    ("human", "Guest reviews:\n\n{context}\n\nQuestion: {question}"),
])

# Step 3: the LLM (reads ANTHROPIC_API_KEY from the environment automatically)
llm = ChatAnthropic(model=MODEL, max_tokens=1024)


def build_chain(city: Optional[str]):
    """The chain: question -> {retrieved reviews + question} -> prompt -> Claude -> text."""
    retrieve = RunnableLambda(lambda question: retrieve_reviews(question, city))
    return (
        {"context": retrieve, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask questions about guest reviews")
    parser.add_argument("question", nargs="*", help="your question")
    parser.add_argument("--city", choices=CITIES, help="only use reviews from this city")
    args = parser.parse_args()

    question = " ".join(args.question) or "What do guests complain about most?"
    scope = args.city.title() if args.city else "all cities"
    print(f"\nQuestion ({scope}): {question}\n")

    # Stream the answer word by word, like a chat interface
    for chunk in build_chain(args.city).stream(question):
        print(chunk, end="", flush=True)
    print("\n")
