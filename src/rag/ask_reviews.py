"""
Ask questions about guest reviews (RAG: retrieval-augmented generation).

  1. Retrieve the most relevant reviews from Pinecone
  2. Pass them to Claude through a LangChain chain
  3. Claude writes an answer based only on those reviews

Run from the project root:
    python src/rag/ask_reviews.py "What do guests complain about most?"
"""
import os
import sys

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
TOP_K = 10                               # how many reviews Claude gets to read
MODEL = "claude-haiku-4-5-20251001"      # fast and cheap; "claude-sonnet-5-5" for higher quality

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index = pc.Index(INDEX_NAME)


def retrieve_reviews(question: str) -> str:
    """Step 1: semantic search in Pinecone, formatted as numbered text for the prompt."""
    results = index.search(
        namespace=NAMESPACE,
        query={"inputs": {"text": question}, "top_k": TOP_K},
        fields=["review_text", "listing_id", "review_date"],
    )
    hits = results["result"]["hits"]
    if not hits:
        return "No relevant reviews found."

    blocks = []
    for i, hit in enumerate(hits, start=1):
        f = hit["fields"]
        blocks.append(
            f"[Review {i}] listing {f['listing_id']}, {f['review_date']}:\n{f['review_text']}"
        )
    return "\n\n".join(blocks)


# Step 2: the prompt that combines the retrieved reviews with the question
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a hospitality analyst. Answer the user's question using only the "
        "guest reviews provided. Reviews may be in any language; always answer in "
        "English. Cite the reviews you rely on by number, e.g. [Review 3]. If the "
        "reviews don't contain enough information to answer, say so instead of "
        "guessing. Keep the answer under 200 words.",
    ),
    ("human", "Guest reviews:\n\n{context}\n\nQuestion: {question}"),
])

# Step 3: the LLM (reads ANTHROPIC_API_KEY from the environment automatically)
llm = ChatAnthropic(model=MODEL, max_tokens=1024)

# The chain: question -> {retrieved reviews + question} -> prompt -> Claude -> plain text
chain = (
    {"context": RunnableLambda(retrieve_reviews), "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What do guests complain about most?"
    print(f"\nQuestion: {question}\n")
    print(chain.invoke(question))
    print()
