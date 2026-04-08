"""
Phase 3: Multi-Agent RAG Pipeline for Building Code Amendments
================================================================

Architecture:
  User Query → Classifier Agent → Route to specialist:
    ├── Factual Agent (single-city, single-section lookup)
    ├── Cross-Jurisdiction Agent (compare 2+ cities)
    ├── Temporal Agent (track changes over time)
    └── Compliance Agent (multi-condition reasoning)
  → Citation Validator → Final Answer

Each agent uses targeted retrieval instead of dumping everything into one prompt.
"""

import re
import httpx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# ─── Config (from environment / Streamlit secrets) ──────────────────────────

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

SUPABASE_KEY = SUPABASE_SERVICE_KEY
OPENAI_KEY = OPENAI_API_KEY
NEO4J_AUTH = (NEO4J_USER, NEO4J_PASSWORD)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

CANONICAL_CITIES = {
    "losangeles": "Los Angeles", "los angeles": "Los Angeles", "la": "Los Angeles",
    "sandiego": "San Diego", "san diego": "San Diego",
    "santaclarita": "Santa Clarita", "santa clarita": "Santa Clarita",
    "phoenix": "Phoenix", "henderson": "Henderson", "irvine": "Irvine",
    "reno": "Reno", "scottsdale": "Scottsdale", "atlanta": "Atlanta",
}

KNOWN_CITIES = list(set(CANONICAL_CITIES.values()))


def normalize_city(name: str) -> str:
    """Normalize city name to canonical form with proper spacing."""
    return CANONICAL_CITIES.get(name.lower().strip(), name)

embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=OPENAI_KEY)
classifier_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=OPENAI_KEY)
answer_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=OPENAI_KEY)
answer_llm_streaming = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=OPENAI_KEY, streaming=True)


# ─── Retrieval Helpers ────────────────────────────────────────────────────────


def _dedupe_by_source(chunks: list, top_k: int, max_per_source: int = 2) -> list:
    """Ensure source-level diversity: max N chunks from the same PDF."""
    source_counts: dict[str, int] = {}
    result = []
    for c in chunks:
        source = c.get("metadata", {}).get("original_filename", "unknown")
        count = source_counts.get(source, 0)
        if count < max_per_source:
            result.append(c)
            source_counts[source] = count + 1
        if len(result) >= top_k:
            break
    return result


def vector_search(query: str, top_k: int = 5, city_filter: str = None) -> list:
    """Vector search with optional city metadata filtering and source diversity."""
    emb = embeddings.embed_query(query)
    fetch_count = top_k * 4  # over-fetch to allow dedup

    if city_filter:
        res = httpx.post(
            f"{SUPABASE_URL}/rest/v1/rpc/match_documents",
            headers=HEADERS,
            json={
                "query_embedding": emb,
                "match_count": fetch_count,
                "filter": {"city": city_filter},
            },
            timeout=30,
        )
        chunks = res.json() if res.status_code == 200 else []

        if not chunks:
            res = httpx.post(
                f"{SUPABASE_URL}/rest/v1/rpc/match_documents",
                headers=HEADERS,
                json={"query_embedding": emb, "match_count": fetch_count},
                timeout=30,
            )
            chunks = res.json() if res.status_code == 200 else []
    else:
        res = httpx.post(
            f"{SUPABASE_URL}/rest/v1/rpc/match_documents",
            headers=HEADERS,
            json={"query_embedding": emb, "match_count": fetch_count},
            timeout=30,
        )
        chunks = res.json() if res.status_code == 200 else []

    return _dedupe_by_source(chunks, top_k)


def chunks_to_context(chunks: list, label: str = "") -> str:
    """Format chunks into context string."""
    if not chunks:
        return f"[No results found{' for ' + label if label else ''}]"
    parts = []
    for c in chunks:
        meta = c.get("metadata", {})
        city = meta.get("city", "unknown")
        source = meta.get("original_filename", "unknown")
        text = c.get("content", "")
        parts.append(f"[{city} | {source}]\n{text}")
    prefix = f"=== {label} ===\n" if label else ""
    return prefix + "\n---\n".join(parts)


# ─── Graph Retrieval ─────────────────────────────────────────────────────────


def graph_retrieve(query: str, cities: list = None) -> str:
    """Retrieve structured context from Neo4j knowledge graph.

    Schema: Jurisdiction, State, CodeFamily, CodeEdition, CodeUnit, AmendmentEvent, SourceFile.
    Relationships: HAS_JURISDICTION, HAS_CODE_EDITION, HAS_EDITION, HAS_CODE_UNIT,
                   AMENDMENT_EVENT, FOR_CODE_FAMILY, CONTAINS_DOCUMENT_UNIT, HAS_SOURCE_FILE.
    """
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return ""

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    except Exception:
        return ""

    parts = []
    try:
        with driver.session() as session:
            # 1. Jurisdiction profiles
            profiles = session.run(
                "MATCH (s:State)-[:HAS_JURISDICTION]->(j:Jurisdiction) "
                "RETURN j.name AS city, s.state_name AS state, s.state_code AS state_code, "
                "       j.population AS pop, j.hazard_type AS hazard "
                "ORDER BY j.name"
            )
            prof_data = [dict(r) for r in profiles]
            if prof_data:
                lines = ["JURISDICTION PROFILES:"]
                for p in prof_data:
                    pop = f"{p['pop']:,}" if p.get("pop") else "unknown"
                    lines.append(f"  {p['city']} ({p['state_code']}): pop = {pop}, hazard = {p.get('hazard', 'N/A')}")
                parts.append("\n".join(lines))

            # 2. Code editions (scoped to cities if provided)
            if cities:
                # Map display names to jurisdiction IDs
                j_ids = session.run(
                    "MATCH (j:Jurisdiction) WHERE j.name IN $cities "
                    "RETURN j.jurisdiction_id AS jid, j.name AS name",
                    cities=cities,
                )
                jid_map = {r["jid"]: r["name"] for r in j_ids}
                if jid_map:
                    editions = session.run(
                        "MATCH (ce:CodeEdition) WHERE ce.jurisdiction_id IN $jids "
                        "RETURN ce.edition_name AS edition, ce.edition_year AS year, "
                        "       ce.code_family_id AS family, ce.jurisdiction_id AS jid "
                        "ORDER BY ce.jurisdiction_id, ce.edition_year",
                        jids=list(jid_map.keys()),
                    )
                    ed_data = [dict(r) for r in editions]
                    if ed_data:
                        lines = ["CODE EDITIONS:"]
                        for e in ed_data:
                            city_name = jid_map.get(e["jid"], e["jid"])
                            lines.append(f"  {city_name} ({e['year']}): {e['edition']} [{e['family']}]")
                        parts.append("\n".join(lines))
            else:
                editions = session.run(
                    "MATCH (ce:CodeEdition) "
                    "RETURN ce.edition_name AS edition, ce.edition_year AS year, "
                    "       ce.code_family_id AS family, ce.jurisdiction_id AS jid "
                    "ORDER BY ce.jurisdiction_id, ce.edition_year"
                )
                ed_data = [dict(r) for r in editions]
                if ed_data:
                    lines = ["CODE EDITIONS:"]
                    for e in ed_data:
                        lines.append(f"  {e['jid']} ({e['year']}): {e['edition']} [{e['family']}]")
                    parts.append("\n".join(lines))

            # 3. Amendment events summary
            ae_data = session.run(
                "MATCH (ae:AmendmentEvent) "
                "WITH ae.code_family_id AS family, ae.year AS year, "
                "     count(*) AS events, sum(CASE WHEN ae.is_amended THEN 1 ELSE 0 END) AS amended "
                "RETURN family, year, events, amended "
                "ORDER BY family, year"
            )
            ae_rows = [dict(r) for r in ae_data]
            if ae_rows:
                lines = ["AMENDMENT EVENTS BY YEAR:"]
                for a in ae_rows:
                    lines.append(f"  {a['family']} {a['year']}: {a['events']} events ({a['amended']} amended)")
                parts.append("\n".join(lines))

            # 4. Code families
            cf_data = session.run("MATCH (cf:CodeFamily) RETURN cf.name AS name, cf.model_family AS model")
            cf_rows = [dict(r) for r in cf_data]
            if cf_rows:
                lines = ["CODE FAMILIES:"]
                for c in cf_rows:
                    lines.append(f"  {c['name']}: model = {c['model']}")
                parts.append("\n".join(lines))

    except Exception as e:
        parts.append(f"[Graph retrieval error: {e}]")
    finally:
        driver.close()

    return "\n\n".join(parts)


def detect_cities(text: str) -> list:
    """Detect city names mentioned in the query, returning canonical names."""
    found = []
    text_lower = text.lower()
    city_variants = {
        "los angeles": "Los Angeles", "la ": "Los Angeles", "l.a.": "Los Angeles",
        "san diego": "San Diego", "phoenix": "Phoenix",
        "henderson": "Henderson", "irvine": "Irvine",
        "reno": "Reno", "santa clarita": "Santa Clarita",
        "scottsdale": "Scottsdale", "atlanta": "Atlanta",
    }
    for name, canonical in city_variants.items():
        if name in text_lower and canonical not in found:
            found.append(canonical)
    return found


# ─── Agent 1: Query Classifier ───────────────────────────────────────────────


def classify_query(question: str) -> dict:
    """Classify query type and extract parameters using fast LLM."""
    response = classifier_llm.invoke(
        "Classify this building code question into ONE category and extract parameters.\n\n"
        "Categories:\n"
        "- factual: single fact lookup (e.g., 'What is the fire rating for X?')\n"
        "- cross_jurisdiction: comparing 2+ cities (e.g., 'How does LA differ from Phoenix?')\n"
        "- temporal: changes over time (e.g., 'What changed between 2019 and 2022?')\n"
        "- compliance: multi-condition requirements (e.g., 'What applies to a building in zone X with hazard Y?')\n\n"
        f"Question: {question}\n\n"
        "Respond with ONLY the category name (one word)."
    )

    category = response.content.strip().lower().replace("'", "").replace('"', '')
    # Normalize
    if "cross" in category or "jurisdiction" in category or "compar" in category:
        category = "cross_jurisdiction"
    elif "temporal" in category or "time" in category or "change" in category:
        category = "temporal"
    elif "compliance" in category or "multi" in category:
        category = "compliance"
    else:
        category = "factual"

    cities = detect_cities(question)

    return {"category": category, "cities": cities}


# ─── Agent 2: Factual Agent ──────────────────────────────────────────────────


def factual_agent(question: str, cities: list) -> str:
    """Handle single-fact lookups with focused retrieval."""
    city_filter = cities[0] if cities else None
    chunks = vector_search(question, top_k=5, city_filter=city_filter)
    context = chunks_to_context(chunks)

    response = answer_llm.invoke(
        "You are a building code expert. Answer this factual question using the provided context.\n\n"
        "RULES:\n"
        "- Base your answer on the context below. Cite specific section numbers and source documents.\n"
        "- If the context contains relevant information, extract and present it even if it only partially answers the question.\n"
        "- If a table in the context contains the data needed, read and cite the specific values.\n"
        "- Do NOT fabricate section numbers or requirements not present in the context.\n"
        "- Only say you cannot answer if the context is truly unrelated to the question.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )
    return response.content


# ─── Agent 3: Cross-Jurisdiction Agent ────────────────────────────────────────


def cross_jurisdiction_agent(question: str, cities: list) -> str:
    """Compare building codes across cities with per-city retrieval + graph context."""

    # If no cities detected, try to infer from question
    if not cities:
        cities_response = classifier_llm.invoke(
            f"Which cities are being compared in this question? List city names only, comma-separated.\n"
            f"Question: {question}\n"
            f"Available cities: Los Angeles, San Diego, Phoenix, Henderson, Irvine, Reno, Santa Clarita, Scottsdale, Atlanta\n"
            f"Answer:"
        )
        for name in cities_response.content.split(","):
            detected = detect_cities(name.strip())
            cities.extend(detected)

    # Get structured graph context (city profiles, timelines, shared sections)
    graph_text = graph_retrieve(question, cities=cities)

    # Retrieve from EACH city separately
    city_contexts = []
    for city in cities[:3]:  # Max 3 cities
        chunks = vector_search(question, top_k=4, city_filter=city)
        city_contexts.append(chunks_to_context(chunks, label=city))

    # Also get general results if fewer than 2 cities
    if len(cities) < 2:
        general_chunks = vector_search(question, top_k=6)
        city_contexts.append(chunks_to_context(general_chunks, label="All Cities"))

    combined_context = "\n\n".join(city_contexts)

    response = answer_llm.invoke(
        "You are a building code expert comparing amendments across US cities.\n\n"
        "RULES:\n"
        "- Base your answer on the KNOWLEDGE GRAPH DATA and RETRIEVED PASSAGES below.\n"
        "- Do NOT fabricate section numbers, ordinance numbers, or code requirements.\n"
        "- If the context contains relevant information, extract and present it.\n"
        "- Use graph data for structural facts (base codes, timelines, profiles) even if passages are sparse.\n\n"
        "Instructions:\n"
        "1. Use the KNOWLEDGE GRAPH DATA for city profiles, base codes, and adoption timelines\n"
        "2. Use the RETRIEVED PASSAGES for specific code section content and amendments\n"
        "3. For EACH city mentioned, describe their specific requirements from the evidence\n"
        "4. Highlight KEY DIFFERENCES between cities\n"
        "5. Cite specific section numbers and amendment sources\n"
        "6. If information for a city is limited, state what you found and what is missing\n\n"
        f"KNOWLEDGE GRAPH DATA:\n{graph_text}\n\n"
        f"RETRIEVED PASSAGES (per-city):\n{combined_context}\n\n"
        f"Question: {question}"
    )
    return response.content


# ─── Agent 4: Temporal Agent ──────────────────────────────────────────────────


def temporal_agent(question: str, cities: list) -> str:
    """Handle questions about code changes over time with graph timeline data."""
    # Extract year references
    years = re.findall(r"20[12]\d", question)

    # Get graph context (adoption timelines are critical for temporal questions)
    graph_text = graph_retrieve(question, cities=cities)

    # Search for each year period
    contexts = []
    if years:
        for year in years[:3]:
            chunks = vector_search(f"{question} {year}", top_k=4)
            contexts.append(chunks_to_context(chunks, label=f"Year {year}"))
    else:
        chunks = vector_search(question, top_k=8)
        contexts.append(chunks_to_context(chunks, label="Timeline"))

    combined = "\n\n".join(contexts)

    response = answer_llm.invoke(
        "You are a building code expert analyzing how codes have changed over time.\n\n"
        "RULES:\n"
        "- Base your answer on the KNOWLEDGE GRAPH DATA and RETRIEVED PASSAGES below.\n"
        "- Do NOT fabricate dates, edition numbers, or adoption timelines.\n"
        "- Use graph data for timeline facts even if passages provide limited detail.\n\n"
        "Instructions:\n"
        "1. Use the KNOWLEDGE GRAPH DATA for the official adoption timeline and code editions\n"
        "2. Use the RETRIEVED PASSAGES for specific amendment content and section details\n"
        "3. Present information chronologically\n"
        "4. Highlight what CHANGED between editions/years based on evidence\n"
        "5. Cite specific ordinance numbers and amendment dates\n"
        "6. If only partial data is available, present what you have and note gaps\n\n"
        f"KNOWLEDGE GRAPH DATA:\n{graph_text}\n\n"
        f"RETRIEVED PASSAGES:\n{combined}\n\n"
        f"Question: {question}"
    )
    return response.content


# ─── Agent 5: Compliance Agent ────────────────────────────────────────────────


def compliance_agent(question: str, cities: list) -> str:
    """Handle multi-condition compliance questions."""
    # Break question into sub-queries for targeted retrieval
    sub_queries_response = classifier_llm.invoke(
        f"Break this compliance question into 2-3 specific sub-questions for targeted search.\n"
        f"Question: {question}\n"
        f"Respond with sub-questions, one per line."
    )
    sub_queries = [q.strip().lstrip("0123456789.-) ") for q in sub_queries_response.content.strip().split("\n") if q.strip()]

    # Retrieve for each sub-query
    all_chunks = []
    for sq in sub_queries[:3]:
        chunks = vector_search(sq, top_k=3, city_filter=cities[0] if cities else None)
        all_chunks.extend(chunks)

    # Deduplicate by content
    seen = set()
    unique_chunks = []
    for c in all_chunks:
        content = c.get("content", "")[:100]
        if content not in seen:
            seen.add(content)
            unique_chunks.append(c)

    context = chunks_to_context(unique_chunks[:8])

    response = answer_llm.invoke(
        "You are a building code compliance expert.\n\n"
        "RULES:\n"
        "- Base your answer on the context below. Do NOT fabricate code sections or requirements.\n"
        "- If the context contains relevant information, extract and present it.\n"
        "- If the context only covers some conditions, answer what you can and note the gaps.\n\n"
        "Instructions:\n"
        "1. Address EACH condition/requirement mentioned in the question using context evidence\n"
        "2. Cite specific code sections for each requirement found in context\n"
        "3. Note any exceptions or special provisions from the context\n"
        "4. Provide a compliance summary based on available evidence\n"
        "5. Note which requirements could not be verified from the context\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )
    return response.content


# ─── Agent 6: Citation Validator ──────────────────────────────────────────────


def validate_citations(answer: str, question: str) -> str:
    """Quick validation pass to catch obvious hallucinations."""
    validation = classifier_llm.invoke(
        "Review this building code answer for accuracy.\n"
        "Check: Are the cited section numbers plausible? Are city names correct?\n"
        "If you find obvious errors, note them. Otherwise say VALID.\n"
        "Be brief (1-2 sentences max).\n\n"
        f"Question: {question}\n"
        f"Answer: {answer[:500]}\n\n"
        f"Validation:"
    )

    validation_text = validation.content.strip()
    if "valid" in validation_text.lower():
        return answer
    else:
        return answer + f"\n\n_Note: {validation_text}_"


# ─── Main Pipeline ────────────────────────────────────────────────────────────


def multi_agent_answer(question: str, return_chunks: bool = False):
    """Full multi-agent RAG pipeline.

    Args:
        question: The user question.
        return_chunks: If True, return (answer, chunks) tuple for eval.

    Returns:
        str or (str, list) depending on return_chunks.
    """

    # Step 1: Classify
    classification = classify_query(question)
    category = classification["category"]
    cities = classification["cities"]

    # Step 2: Route to specialist agent (collect chunks for eval)
    collected_chunks = []
    if category == "cross_jurisdiction":
        answer = cross_jurisdiction_agent(question, cities)
        # Retrieve chunks for eval context
        for city in cities[:3]:
            collected_chunks.extend(vector_search(question, top_k=3, city_filter=city))
    elif category == "temporal":
        answer = temporal_agent(question, cities)
        collected_chunks.extend(vector_search(question, top_k=5))
    elif category == "compliance":
        answer = compliance_agent(question, cities)
        collected_chunks.extend(vector_search(question, top_k=5, city_filter=cities[0] if cities else None))
    else:
        city_filter = cities[0] if cities else None
        answer = factual_agent(question, cities)
        collected_chunks.extend(vector_search(question, top_k=5, city_filter=city_filter))

    # Step 3: Validate citations
    answer = validate_citations(answer, question)

    if return_chunks:
        return answer, collected_chunks
    return answer


# ─── CLI Test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "How do Los Angeles and Phoenix approach fire protection amendments differently?"

    print(f"Question: {question}")
    print(f"{'='*60}")

    classification = classify_query(question)
    print(f"Category: {classification['category']}")
    print(f"Cities: {classification['cities']}")
    print()

    answer = multi_agent_answer(question)
    print(answer)


# ─── Streaming Pipeline ─────────────────────────────────────────────────────


def _build_prompt_for_agent(question: str, category: str, cities: list) -> tuple[str, list]:
    """Build the LLM prompt and collect chunks for a given question category.
    Returns (prompt_string, chunks_list)."""
    if category == "cross_jurisdiction":
        if not cities:
            cities_response = classifier_llm.invoke(
                f"Which cities are being compared? List city names only, comma-separated.\n"
                f"Question: {question}\n"
                f"Available: Los Angeles, San Diego, Phoenix, Henderson, Irvine, Reno, Santa Clarita, Scottsdale, Atlanta\n"
                f"Answer:"
            )
            for name in cities_response.content.split(","):
                detected = detect_cities(name.strip())
                cities.extend(detected)

        graph_text = graph_retrieve(question, cities=cities)
        city_contexts = []
        all_chunks = []
        for city in cities[:3]:
            chunks = vector_search(question, top_k=4, city_filter=city)
            all_chunks.extend(chunks)
            city_contexts.append(chunks_to_context(chunks, label=city))
        if len(cities) < 2:
            general = vector_search(question, top_k=6)
            all_chunks.extend(general)
            city_contexts.append(chunks_to_context(general, label="All Cities"))
        combined = "\n\n".join(city_contexts)

        prompt = (
            "You are a building code expert comparing amendments across US cities.\n\n"
            "RULES:\n"
            "- Base your answer on the KNOWLEDGE GRAPH DATA and RETRIEVED PASSAGES below.\n"
            "- Do NOT fabricate section numbers, ordinance numbers, or code requirements.\n"
            "- If the context contains relevant information, extract and present it.\n"
            "- Use graph data for structural facts (base codes, timelines, profiles) even if passages are sparse.\n\n"
            "Instructions:\n"
            "1. Use the KNOWLEDGE GRAPH DATA for city profiles, base codes, and adoption timelines\n"
            "2. Use the RETRIEVED PASSAGES for specific code section content and amendments\n"
            "3. For EACH city mentioned, describe their specific requirements from the evidence\n"
            "4. Highlight KEY DIFFERENCES between cities\n"
            "5. Cite specific section numbers and amendment sources\n"
            "6. If information for a city is limited, state what you found and what is missing\n\n"
            f"KNOWLEDGE GRAPH DATA:\n{graph_text}\n\n"
            f"RETRIEVED PASSAGES (per-city):\n{combined}\n\n"
            f"Question: {question}"
        )
        return prompt, all_chunks

    elif category == "temporal":
        graph_text = graph_retrieve(question, cities=cities)
        years = re.findall(r"20[12]\d", question)
        contexts = []
        all_chunks = []
        if years:
            for year in years[:3]:
                chunks = vector_search(f"{question} {year}", top_k=4)
                all_chunks.extend(chunks)
                contexts.append(chunks_to_context(chunks, label=f"Year {year}"))
        else:
            chunks = vector_search(question, top_k=8)
            all_chunks.extend(chunks)
            contexts.append(chunks_to_context(chunks, label="Timeline"))
        combined = "\n\n".join(contexts)

        prompt = (
            "You are a building code expert analyzing how codes have changed over time.\n\n"
            "RULES:\n"
            "- Base your answer on the KNOWLEDGE GRAPH DATA and RETRIEVED PASSAGES below.\n"
            "- Do NOT fabricate dates, edition numbers, or adoption timelines.\n"
            "- Use graph data for timeline facts even if passages provide limited detail.\n\n"
            "Instructions:\n"
            "1. Use the KNOWLEDGE GRAPH DATA for the official adoption timeline and code editions\n"
            "2. Use the RETRIEVED PASSAGES for specific amendment content and section details\n"
            "3. Present information chronologically\n"
            "4. Highlight what CHANGED between editions/years based on evidence\n"
            "5. Cite specific ordinance numbers and amendment dates\n"
            "6. If only partial data is available, present what you have and note gaps\n\n"
            f"KNOWLEDGE GRAPH DATA:\n{graph_text}\n\n"
            f"RETRIEVED PASSAGES:\n{combined}\n\n"
            f"Question: {question}"
        )
        return prompt, all_chunks

    elif category == "compliance":
        sub_queries_response = classifier_llm.invoke(
            f"Break this compliance question into 2-3 specific sub-questions.\n"
            f"Question: {question}\nRespond with sub-questions, one per line."
        )
        sub_queries = [q.strip().lstrip("0123456789.-) ") for q in sub_queries_response.content.strip().split("\n") if q.strip()]
        all_chunks = []
        for sq in sub_queries[:3]:
            chunks = vector_search(sq, top_k=3, city_filter=cities[0] if cities else None)
            all_chunks.extend(chunks)
        seen = set()
        unique = [c for c in all_chunks if c.get("content", "")[:100] not in seen and not seen.add(c.get("content", "")[:100])]
        context = chunks_to_context(unique[:8])

        prompt = (
            "You are a building code compliance expert.\n\n"
            "RULES:\n"
            "- Base your answer on the context below. Do NOT fabricate code sections or requirements.\n"
            "- If the context contains relevant information, extract and present it.\n"
            "- If the context only covers some conditions, answer what you can and note the gaps.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )
        return prompt, unique[:8]

    else:  # factual
        city_filter = cities[0] if cities else None
        chunks = vector_search(question, top_k=5, city_filter=city_filter)
        context = chunks_to_context(chunks)

        prompt = (
            "You are a building code expert. Answer this factual question using the provided context.\n\n"
            "RULES:\n"
            "- Base your answer on the context below. Cite specific section numbers and source documents.\n"
            "- If the context contains relevant information, extract and present it even if it only partially answers the question.\n"
            "- If a table in the context contains the data needed, read and cite the specific values.\n"
            "- Do NOT fabricate section numbers or requirements not present in the context.\n"
            "- Only say you cannot answer if the context is truly unrelated to the question.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )
        return prompt, chunks


def stream_multi_agent_answer(question: str):
    """Streaming version: yields tokens as they generate.

    Usage in Streamlit:
        st.write_stream(stream_multi_agent_answer(question))
    """
    # Step 1: Classify (fast, non-streaming)
    classification = classify_query(question)
    category = classification["category"]
    cities = classification["cities"]

    # Step 2: Build prompt with retrieval (non-streaming)
    prompt, _ = _build_prompt_for_agent(question, category, cities)

    # Step 3: Stream the answer
    for chunk in answer_llm_streaming.stream(prompt):
        if chunk.content:
            yield chunk.content
