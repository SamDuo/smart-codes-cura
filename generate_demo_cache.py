"""
Generate pre-computed demo answers for common building code questions.
Run this ONCE to create demo_cache.json with embeddings + answers.

Usage:
    python generate_demo_cache.py
"""

import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from config import OPENAI_API_KEY
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from multi_agent_rag import multi_agent_answer

embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=OPENAI_API_KEY)

DEMO_QUESTIONS = [
    # Factual questions
    "What is the fire rating requirement for exterior walls in Los Angeles?",
    "What are the seismic design requirements in Phoenix?",
    "What is the minimum ceiling height for residential buildings in San Diego?",
    "What are the egress requirements for high-rise buildings in Atlanta?",
    "What is the wind speed design requirement in Henderson?",
    "What fire sprinkler requirements does Irvine have?",
    "What are the accessibility requirements in Reno building codes?",
    "What is the energy code requirement for new construction in Scottsdale?",
    "What are the plumbing code requirements in Santa Clarita?",
    "What structural loads are required for roofs in Phoenix?",

    # Cross-jurisdiction comparisons
    "How do Los Angeles and Phoenix approach fire protection amendments differently?",
    "Compare seismic requirements between Los Angeles and San Diego.",
    "How do building codes differ between Atlanta and Phoenix?",
    "What are the differences in energy code requirements between Irvine and Scottsdale?",
    "Compare fire sprinkler requirements across Los Angeles, Phoenix, and Atlanta.",
    "How do Henderson and Reno differ in their building code amendments?",

    # Temporal questions
    "How have fire codes changed in Los Angeles over the years?",
    "What building code changes occurred in Phoenix between 2019 and 2022?",
    "How has the energy code evolved in San Diego?",
    "What amendments were adopted in Atlanta in recent code cycles?",

    # Compliance questions
    "What fire protection requirements apply to a 5-story commercial building in Los Angeles?",
    "What are the combined structural and fire requirements for a hospital in Phoenix?",
    "What codes apply to mixed-use buildings in downtown San Diego?",
    "What are the requirements for a building in a high seismic zone in Irvine?",
    "What compliance requirements exist for a school building in Atlanta?",

    # General questions
    "Which cities have adopted the 2021 IBC?",
    "What base building code does each city use?",
    "Which jurisdictions have the strictest fire codes?",
    "What are the most common local amendments across all cities?",
    "How many cities require fire sprinklers in single-family homes?",
]


def generate():
    output_path = os.path.join(os.path.dirname(__file__), "demo_cache.json")
    results = []

    # Load existing results if any (for resume)
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            results = json.load(f)
        done_questions = {r["question"] for r in results}
        print(f"Loaded {len(results)} existing answers, resuming...")
    else:
        done_questions = set()

    remaining = [q for q in DEMO_QUESTIONS if q not in done_questions]
    total = len(DEMO_QUESTIONS)

    for i, question in enumerate(remaining):
        idx = total - len(remaining) + i + 1
        print(f"\n[{idx}/{total}] {question}")
        t0 = time.time()

        try:
            answer = multi_agent_answer(question)
            emb = embeddings.embed_query(question)

            results.append({
                "question": question,
                "answer": answer,
                "embedding": emb,
            })
            elapsed = time.time() - t0
            print(f"  Done in {elapsed:.1f}s ({len(answer)} chars)")

            # Save after each question (resume-safe)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    print(f"\nSaved {len(results)} answers to {output_path}")


if __name__ == "__main__":
    generate()
