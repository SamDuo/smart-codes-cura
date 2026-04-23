"""
Generate cross-jurisdiction and multi-hop benchmark queries using the existing
Neo4j schema (Jurisdiction, CodeUnit, AmendmentEvent, CodeEdition, Hazard, etc.)
and Supabase vector search.

Aligned with Lincoln Institute research questions:
1. How do codes affect housing supply, affordability, and resilience?
2. Do codes better protect from climate-related risks?
3. Cross-jurisdictional comparison of amendment patterns
"""
import json
import os

import httpx
from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
OPENAI_KEY = os.environ["OPENAI_API_KEY"]
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=OPENAI_KEY)
llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=OPENAI_KEY)


def vector_search(query, top_k=5):
    emb = embeddings.embed_query(query)
    res = httpx.post(f"{SUPABASE_URL}/rest/v1/rpc/match_documents", headers=HEADERS,
                     json={"query_embedding": emb, "match_count": top_k}, timeout=30)
    return res.json() if res.status_code == 200 else []


def graph_query(cypher, **params):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        result = session.run(cypher, **params)
        data = [dict(r) for r in result]
    driver.close()
    return data


def extract_json(text):
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    return None


def generate_all():
    qa_pairs = []

    # ═══════════════════════════════════════════════════════════════
    # CROSS-JURISDICTION QUERIES (from Neo4j graph structure)
    # ═══════════════════════════════════════════════════════════════

    # 1. City profiles and hazard types
    jurisdictions = graph_query(
        "MATCH (j:Jurisdiction) "
        "RETURN j.name AS city, j.state_code AS state, j.population AS pop, j.hazard_type AS hazard "
        "ORDER BY j.population DESC"
    )
    if jurisdictions:
        qa_pairs.append({
            "question": "Which cities are in our building code dataset, what states are they in, and what are their primary hazard types?",
            "category": "cross_jurisdiction",
            "answer": "; ".join(f"{j['city']} ({j['state']}, pop {j['pop']:,}, hazard: {j['hazard']})" for j in jurisdictions),
            "facts": [j["city"] for j in jurisdictions] + [j.get("hazard", "") for j in jurisdictions if j.get("hazard")],
            "citations": [],
        })
        print(f"  1. City profiles: {len(jurisdictions)} cities")

    # 2. Amendment frequency comparison
    freq_data = graph_query(
        "MATCH (j:Jurisdiction)-[:AMENDMENT_EVENT]->(ae:AmendmentEvent) "
        "RETURN j.name AS city, count(ae) AS events, "
        "       sum(CASE WHEN ae.is_amended THEN 1 ELSE 0 END) AS with_amendments, "
        "       min(ae.year) AS first_year, max(ae.year) AS latest_year "
        "ORDER BY events DESC"
    )
    if freq_data:
        qa_pairs.append({
            "question": "Compare the amendment activity across cities. Which city has adopted or amended its building code most frequently?",
            "category": "cross_jurisdiction",
            "answer": "; ".join(f"{d['city']}: {d['events']} events ({d['first_year']}-{d['latest_year']}), {d['with_amendments']} with local amendments" for d in freq_data),
            "facts": [freq_data[0]["city"], str(freq_data[0]["events"])] + [d["city"] for d in freq_data],
            "citations": [],
        })
        print(f"  2. Amendment frequency: {len(freq_data)} cities")

    # 3. Code editions comparison
    editions = graph_query(
        "MATCH (ce:CodeEdition) "
        "RETURN ce.jurisdiction_id AS jurisdiction, ce.edition_name AS name, ce.edition_year AS year "
        "ORDER BY ce.jurisdiction_id, ce.edition_year"
    )
    if editions:
        qa_pairs.append({
            "question": "What building code editions have been adopted by Los Angeles and San Diego? List them with years.",
            "category": "cross_jurisdiction",
            "answer": "; ".join(f"{e['jurisdiction']}: {e['name']} ({e['year']})" for e in editions),
            "facts": [e["name"] for e in editions] + [str(e["year"]) for e in editions],
            "citations": [],
        })
        print(f"  3. Code editions: {len(editions)} editions")

    # 4. Shared code sections between LA and San Diego
    shared = graph_query(
        "MATCH (j1:Jurisdiction)-[:HAS_SOURCE_FILE]->()-[:CONTAINS_DOCUMENT_UNIT]->()-[:HAS_CODE_UNIT]->(cu:CodeUnit) "
        "WHERE cu.canonical_ref IS NOT NULL "
        "WITH cu.canonical_ref AS ref, cu.title AS title, collect(DISTINCT j1.name) AS cities "
        "WHERE size(cities) >= 2 "
        "RETURN ref, title, cities "
        "ORDER BY ref LIMIT 15"
    )
    if shared:
        qa_pairs.append({
            "question": "Which building code sections are addressed by multiple cities in our dataset? List the shared sections.",
            "category": "cross_jurisdiction",
            "answer": "; ".join(f"Section {s['ref']} ({s['title']}): {', '.join(s['cities'])}" for s in shared[:10]),
            "facts": [s["ref"] for s in shared[:5]] + list(set(c for s in shared for c in s["cities"])),
            "citations": [f"Section {s['ref']}" for s in shared[:5]],
        })
        print(f"  4. Shared sections: {len(shared)} sections across cities")

    # 5. Hazard-specific queries
    hazards = graph_query(
        "MATCH (j:Jurisdiction)-[:AFFECTS_HAZARD]->(h:Hazard) "
        "RETURN j.name AS city, h.name AS hazard "
        "ORDER BY h.name"
    )
    if hazards:
        qa_pairs.append({
            "question": "Which cities in our dataset are affected by which natural hazards according to the knowledge graph?",
            "category": "climate_resilience",
            "answer": "; ".join(f"{h['city']}: {h['hazard']}" for h in hazards),
            "facts": [h["city"] for h in hazards] + [h["hazard"] for h in hazards],
            "citations": [],
        })
        print(f"  5. Hazard assignments: {len(hazards)} city-hazard links")

    # ═══════════════════════════════════════════════════════════════
    # CROSS-JURISDICTION QUERIES (from vector search + LLM)
    # ═══════════════════════════════════════════════════════════════

    comparison_topics = [
        ("Los Angeles", "Phoenix", "fire protection sprinkler requirements"),
        ("Los Angeles", "San Diego", "seismic earthquake design requirements"),
        ("Los Angeles", "Henderson", "building code adoption approach IBC CBC"),
        ("Irvine", "Santa Clarita", "energy conservation code requirements"),
        ("Reno", "Henderson", "residential code sprinkler amendment"),
        ("Phoenix", "Scottsdale", "building code amendment differences"),
    ]

    for city1, city2, topic in comparison_topics:
        chunks = vector_search(f"{city1} {city2} {topic}", top_k=6)
        if not chunks:
            continue
        context = "\n---\n".join(
            f"[{c.get('metadata',{}).get('city','?')}] {c.get('content','')[:400]}"
            for c in chunks[:4]
        )
        response = llm.invoke(
            f"Generate a verified QA pair comparing {city1} and {city2} building code amendments on: {topic}.\n"
            f"Answer based ONLY on the text. State what each city does differently.\n"
            f'JSON: {{"question": "...", "answer": "...", "facts": [...], "citations": [...]}}\n\n'
            f"Text:\n{context}"
        )
        qa = extract_json(response.content)
        if qa:
            qa["category"] = "cross_jurisdiction"
            qa_pairs.append(qa)
            print(f"  Cross: {city1} vs {city2} on {topic[:30]}")

    # ═══════════════════════════════════════════════════════════════
    # TEMPORAL QUERIES (from Neo4j amendment events)
    # ═══════════════════════════════════════════════════════════════

    for j in jurisdictions[:4]:  # Top 4 cities by population
        timeline = graph_query(
            "MATCH (j:Jurisdiction {name: $city})-[:AMENDMENT_EVENT]->(ae:AmendmentEvent) "
            "WHERE ae.is_amended = true "
            "RETURN ae.year AS year, ae.code_family_id AS family, ae.source_value AS edition "
            "ORDER BY ae.year",
            city=j["city"],
        )
        if timeline:
            qa_pairs.append({
                "question": f"What is the complete timeline of building code amendments adopted by {j['city']}?",
                "category": "temporal",
                "answer": f"{j['city']} amendments: " + "; ".join(f"{t['year']}: {t['edition']} ({t['family']})" for t in timeline),
                "facts": [j["city"]] + [str(t["year"]) for t in timeline],
                "citations": [],
            })
            print(f"  Temporal: {j['city']} ({len(timeline)} amendments)")

    # ═══════════════════════════════════════════════════════════════
    # MULTI-HOP QUERIES (from Neo4j graph traversals)
    # ═══════════════════════════════════════════════════════════════

    # Multi-hop: Jurisdiction → SourceFile → DocumentUnit → CodeUnit
    multi_hop = graph_query(
        "MATCH (j:Jurisdiction)-[:HAS_SOURCE_FILE]->(sf:SourceFile)-[:CONTAINS_DOCUMENT_UNIT]->(du:DocumentUnit)-[:HAS_CODE_UNIT]->(cu:CodeUnit) "
        "WHERE cu.text IS NOT NULL AND size(cu.text) > 100 "
        "RETURN j.name AS city, sf.filename AS file, cu.canonical_ref AS ref, cu.title AS title, substring(cu.text, 0, 300) AS text_preview "
        "ORDER BY rand() LIMIT 6"
    )

    for item in multi_hop:
        response = llm.invoke(
            f"Generate a multi-hop question from this building code data that requires connecting "
            f"a city to a specific code section through the document structure.\n\n"
            f"City: {item['city']}, File: {item['file']}, Section: {item['ref']} ({item['title']})\n"
            f"Text: {item['text_preview']}\n\n"
            f"The question should require knowing BOTH which city this applies to AND the specific code requirement.\n"
            f'JSON: {{"question": "...", "answer": "...", "facts": [...], "citations": [...]}}'
        )
        qa = extract_json(response.content)
        if qa:
            qa["category"] = "multi_hop"
            qa_pairs.append(qa)
            print(f"  Multi-hop: {item['city']} Section {item['ref']}")

    # ═══════════════════════════════════════════════════════════════
    # CLIMATE RESILIENCE QUERIES (Lincoln Institute aligned)
    # ═══════════════════════════════════════════════════════════════

    climate_questions = [
        "Which cities have adopted amendments addressing wildfire or fire hazard protection?",
        "How do seismic design requirements differ between California and other states in our dataset?",
        "Which cities have the most recent building code adoptions, and does code recency correlate with hazard exposure?",
    ]

    for question in climate_questions:
        chunks = vector_search(question, top_k=5)
        if not chunks:
            continue
        context = "\n---\n".join(
            f"[{c.get('metadata',{}).get('city','?')}] {c.get('content','')[:300]}"
            for c in chunks[:4]
        )
        response = llm.invoke(
            f"Answer based ONLY on the text. Include city names and code sections.\n"
            f'JSON: {{"answer": "...", "facts": [...], "citations": [...]}}\n\n'
            f"Question: {question}\nText:\n{context}"
        )
        qa = extract_json(response.content)
        if qa:
            qa["question"] = question
            qa["category"] = "climate_resilience"
            qa_pairs.append(qa)
            print(f"  Climate: {question[:50]}...")

    return qa_pairs


def main():
    print("GENERATING CROSS-JURISDICTION & MULTI-HOP BENCHMARKS")
    print("=" * 60)

    qa_pairs = generate_all()

    # Load existing and merge
    try:
        with open("ground_truth_qa.json") as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = []

    combined = existing + qa_pairs
    with open("ground_truth_qa.json", "w") as f:
        json.dump(combined, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {len(combined)} queries ({len(existing)} existing + {len(qa_pairs)} new)")
    cats = {}
    for q in combined:
        cat = q.get("category", "factual_lookup")
        cats[cat] = cats.get(cat, 0) + 1
    for cat, count in sorted(cats.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
