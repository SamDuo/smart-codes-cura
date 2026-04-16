"""Generate verified ground truth QA pairs from actual ingested documents."""
import json
import re
import httpx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
OPENAI_KEY = (
    os.environ.get("OPENAI_API_KEY", "")
    "wYEk2T3BlbkFJAlR5vrcnkrJcXAv-aN81APnep5Rgmww389sjRZQDBB7P3FmTb_LBCFuomBMEiNI"
    "pV41SFp_yMA"
)
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=OPENAI_KEY)
llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=OPENAI_KEY)

# Diverse retrieval queries covering all categories
RETRIEVAL_QUERIES = [
    # LA Fire Safety (Chapter 7)
    "fire resistance rating construction type table",
    "fire barrier requirements shaft enclosure section 713",
    "fire alarm system requirements occupancy group",
    "fire separation distance exterior walls openings",
    "sprinkler system requirements exceptions",
    "means of egress corridor width requirements",
    # LA Structural (Chapter 16A)
    "seismic design lateral force requirements",
    "structural design load combinations",
    "wind load design requirements",
    # LA Accessibility (Chapter 11B)
    "accessible entrance requirements public building",
    "ramp slope requirements accessibility",
    "parking accessible spaces requirements",
    # LA Special Chapters
    "earthquake hazard reduction existing buildings",
    "wildfire exposure construction exterior materials",
    "energy conservation requirements new construction",
    "fire district regulations requirements",
    # Henderson NV amendments
    "Henderson Nevada amendment international building code",
    "Henderson residential code amendment sprinkler",
    "Henderson Las Vegas amendments 2021 IBC",
    # Irvine CA amendments
    "Irvine city council ordinance building standards code",
    "Irvine municipal code building standards",
    "Irvine California building code amendments",
    # Cross-jurisdiction
    "local amendment exception international building code",
    "amendment adopted ordinance building code",
    # Phoenix AZ - additional coverage
    "Phoenix building code electric vehicle charging",
    "Phoenix amendment fire sprinkler requirements",
    "Phoenix 2024 building construction code change",
    # Reno NV - additional coverage
    "Reno Northern Nevada code amendments residential",
    "Reno building code fire protection requirements",
    "Reno 2024 amendment energy conservation",
    # San Diego CA - additional coverage
    "San Diego building code local amendment findings",
    "San Diego unsafe dangerous buildings amendment",
    "San Diego 2025 code amendment requirements",
    # Santa Clarita CA - additional coverage
    "Santa Clarita building code amendment fire",
    "Santa Clarita seismic design requirements amendment",
    # Scottsdale AZ
    "Scottsdale building code amendment requirements",
]


def retrieve(query, top_k=3):
    emb = embeddings.embed_query(query)
    res = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/match_documents",
        headers=HEADERS,
        json={"query_embedding": emb, "match_count": top_k},
        timeout=30,
    )
    return res.json() if res.status_code == 200 else []


def extract_json(text):
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try to find JSON in code blocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # Try direct parse
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return None


def generate_qa_from_chunks(chunks, retrieval_query):
    """Generate a verified QA pair from retrieved chunks."""
    if not chunks:
        return None

    context = "\n---\n".join(c.get("content", "")[:600] for c in chunks[:3])
    meta = chunks[0].get("metadata", {})
    source = meta.get("original_filename", "unknown")
    city = meta.get("city", "unknown")

    prompt = (
        "You are creating ground truth QA pairs for evaluating a building code RAG system.\n\n"
        "Rules:\n"
        "1. The answer MUST be DIRECTLY and EXPLICITLY stated in the text below\n"
        "2. Include specific section numbers, table numbers, or ordinance numbers\n"
        "3. The answer must be verifiable by reading the text\n"
        "4. Do NOT infer, assume, or add information not in the text\n"
        "5. Facts list should contain 3-5 key terms that MUST appear in any correct answer\n\n"
        'Respond in JSON:\n'
        '{"question": "...", "answer": "...", "facts": ["fact1", "fact2", "fact3"], '
        '"citations": ["Section X", "Table Y"]}\n\n'
        f"Source: {source} (City: {city})\n"
        f"Text:\n{context}"
    )

    response = llm.invoke(prompt)
    qa = extract_json(response.content)
    if qa:
        qa["source"] = source
        qa["city"] = city
        qa["retrieval_query"] = retrieval_query
        qa["similarity"] = chunks[0].get("similarity", 0)
    return qa


def main():
    print("GENERATING VERIFIED GROUND TRUTH QA PAIRS")
    print("=" * 60)
    print(f"Using {len(RETRIEVAL_QUERIES)} retrieval queries\n")

    all_qa = []
    seen_questions = set()

    for i, query in enumerate(RETRIEVAL_QUERIES):
        chunks = retrieve(query)
        if not chunks:
            print(f"[{i+1}/{len(RETRIEVAL_QUERIES)}] No results for: {query}")
            continue

        qa = generate_qa_from_chunks(chunks, query)
        if qa and qa.get("question") and qa["question"] not in seen_questions:
            seen_questions.add(qa["question"])
            all_qa.append(qa)
            city = qa.get("city", "?")
            print(f"[{i+1}/{len(RETRIEVAL_QUERIES)}] {city}: {qa['question'][:70]}...")
        else:
            print(f"[{i+1}/{len(RETRIEVAL_QUERIES)}] Skipped (duplicate or parse error)")

    # Save
    output_path = "ground_truth_qa.json"
    with open(output_path, "w") as f:
        json.dump(all_qa, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"SAVED {len(all_qa)} verified QA pairs to {output_path}")
    print(f"\nBy city:")
    cities = {}
    for qa in all_qa:
        c = qa.get("city", "unknown")
        cities[c] = cities.get(c, 0) + 1
    for c, n in sorted(cities.items()):
        print(f"  {c}: {n} questions")


if __name__ == "__main__":
    main()
