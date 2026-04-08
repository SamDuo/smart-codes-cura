"""
GT CURA Policy Intelligence Module
=====================================
Investor demo: Cross-jurisdiction building code amendment intelligence
powered by hybrid RAG (vector search + knowledge graph).

8 cities | 41 amendment documents | 2010-2026 | 12,000+ indexed passages
"""

import os
import json
import time

import streamlit as st
import httpx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import AIMessage, HumanMessage

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="GT CURA | Policy Intelligence",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Secrets ──────────────────────────────────────────────────────────────────

def get_secret(name):
    if name in st.secrets:
        return st.secrets[name]
    st.error(f"Missing secret: {name}")
    st.stop()

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_SERVICE_KEY")
OPENAI_KEY = get_secret("OPENAI_API_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=OPENAI_KEY)

# ─── City Data ────────────────────────────────────────────────────────────────

CITIES = {
    "Los Angeles": {"state": "CA", "pop": "3.9M", "hazard": "Wildfire, Seismic", "base": "CBC", "docs": 9, "years": "2011-2026"},
    "San Diego": {"state": "CA", "pop": "1.4M", "hazard": "Wildfire, Coastal Flood", "base": "CBC", "docs": 5, "years": "2016-2025"},
    "Phoenix": {"state": "AZ", "pop": "1.6M", "hazard": "Extreme Heat", "base": "IBC", "docs": 4, "years": "2018-2024"},
    "Irvine": {"state": "CA", "pop": "308K", "hazard": "Seismic", "base": "CBC", "docs": 5, "years": "2010-2025"},
    "Henderson": {"state": "NV", "pop": "325K", "hazard": "Seismic", "base": "IBC", "docs": 8, "years": "2013-2024"},
    "Santa Clarita": {"state": "CA", "pop": "229K", "hazard": "Wildfire", "base": "CBC", "docs": 5, "years": "2013-2025"},
    "Reno": {"state": "NV", "pop": "264K", "hazard": "Seismic, Wildfire", "base": "IBC", "docs": 3, "years": "2012-2024"},
    "Scottsdale": {"state": "AZ", "pop": "241K", "hazard": "Extreme Heat", "base": "IBC", "docs": 1, "years": "2021"},
}

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #6c757d;
        margin-top: -10px;
        margin-bottom: 20px;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        text-align: center;
    }
    .metric-number {
        font-size: 2rem;
        font-weight: 700;
    }
    .metric-label {
        font-size: 0.85rem;
        opacity: 0.9;
    }
    .city-chip {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.8rem;
        margin: 2px;
        background: #e8eaf6;
        color: #283593;
    }
    .stChatMessage {
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### **POLYMETRON**")
    st.markdown("*Policy Intelligence Module*")
    st.divider()

    st.markdown("#### Coverage")
    st.markdown(f"**{len(CITIES)} Cities** across 3 states")

    for city, info in CITIES.items():
        with st.expander(f"{city}, {info['state']}"):
            st.caption(f"Pop: {info['pop']} | Base: {info['base']}")
            st.caption(f"Hazards: {info['hazard']}")
            st.caption(f"Docs: {info['docs']} | Years: {info['years']}")

    st.divider()
    st.markdown("#### Stats")
    st.metric("Amendment Documents", "41")
    st.metric("Indexed Passages", "12,000+")
    st.metric("Code Sections Tracked", "11,163")
    st.metric("Amendment Events", "2,550")

    st.divider()
    st.caption("Powered by GT CURA")
    st.caption("Hybrid RAG: Vector Search + Knowledge Graph")

# ─── Header ───────────────────────────────────────────────────────────────────

col_logo, col_title = st.columns([1, 6])
with col_logo:
    logo_path = os.path.join(os.path.dirname(__file__), "..", "gt_cura_logo.jpg")
    if os.path.exists(logo_path):
        st.image(logo_path, width=80)
with col_title:
    st.markdown('<p class="main-header">Policy Intelligence</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Cross-jurisdiction building code amendment analysis for 8 US cities</p>', unsafe_allow_html=True)

# ─── Metrics Row ──────────────────────────────────────────────────────────────

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Cities", "8", help="Henderson, Irvine, LA, Phoenix, Reno, San Diego, Santa Clarita, Scottsdale")
with m2:
    st.metric("States", "CA, NV, AZ")
with m3:
    st.metric("Time Span", "2010-2026")
with m4:
    st.metric("Hazard Types", "4", help="Wildfire, Seismic, Extreme Heat, Coastal Flood")

st.divider()

# ─── Preset Queries ───────────────────────────────────────────────────────────

st.markdown("#### Try these queries")
preset_cols = st.columns(3)

PRESETS = [
    ("Compare fire codes", "How do Los Angeles and Phoenix approach fire protection amendments differently?"),
    ("Seismic requirements", "What seismic design requirements apply in California cities vs Nevada cities?"),
    ("Code recency", "Which cities have the most recent building code adoptions, and how current are they?"),
    ("EV charging", "What do Phoenix's 2024 amendments say about electric vehicle charging stations?"),
    ("Wildfire zones", "Which cities have adopted amendments specifically addressing wildfire hazard zones?"),
    ("Amendment frequency", "Compare the amendment activity across all 8 cities. Who updates most frequently?"),
]

selected_preset = None
for i, (label, query) in enumerate(PRESETS):
    col = preset_cols[i % 3]
    if col.button(f"  {label}  ", key=f"preset_{i}", use_container_width=True):
        selected_preset = query

# ─── Retrieval Functions ──────────────────────────────────────────────────────


def vector_retrieve(query: str, top_k: int = 8) -> list:
    """Retrieve relevant passages from Supabase vector store."""
    query_embedding = embeddings.embed_query(query)
    res = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/match_documents",
        headers=HEADERS,
        json={"query_embedding": query_embedding, "match_count": top_k},
        timeout=30,
    )
    return res.json() if res.status_code == 200 else []


def get_graph_context(query: str) -> str:
    """Get structured context from Neo4j knowledge graph."""
    try:
        import os
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            os.environ.get("NEO4J_URI", ""),
            auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "")),
        )
        parts = []
        with driver.session() as session:
            # Jurisdiction profiles
            r = session.run(
                "MATCH (j:Jurisdiction) "
                "RETURN j.name AS city, j.state_code AS state, j.population AS pop, j.hazard_type AS hazard"
            )
            profiles = [dict(rec) for rec in r]
            if profiles:
                parts.append("CITY PROFILES: " + "; ".join(
                    f"{p['city']} ({p['state']}, hazard: {p['hazard']})" for p in profiles
                ))

            # Amendment timelines
            r = session.run(
                "MATCH (j:Jurisdiction)-[:AMENDMENT_EVENT]->(ae:AmendmentEvent) "
                "WHERE ae.is_amended = true "
                "RETURN j.name AS city, ae.year AS year, ae.source_value AS edition "
                "ORDER BY j.name, ae.year"
            )
            events = [dict(rec) for rec in r]
            if events:
                by_city = {}
                for e in events:
                    by_city.setdefault(e["city"], []).append(f"{e['year']}: {e['edition']}")
                parts.append("AMENDMENT TIMELINES: " + "; ".join(
                    f"{city}: {', '.join(edits)}" for city, edits in by_city.items()
                ))

            # Code editions
            r = session.run(
                "MATCH (ce:CodeEdition) "
                "RETURN ce.jurisdiction_id AS jurisdiction, ce.edition_name AS name, ce.edition_year AS year "
                "ORDER BY ce.edition_year"
            )
            editions = [dict(rec) for rec in r]
            if editions:
                parts.append("CODE EDITIONS: " + "; ".join(
                    f"{e['name']} ({e['year']})" for e in editions
                ))

        driver.close()
        return "\n".join(parts) if parts else ""
    except Exception:
        return ""


def generate_answer(query: str) -> str:
    """Full hybrid RAG pipeline: graph context + vector retrieval + GPT-4o."""
    # Get graph context
    graph_ctx = get_graph_context(query)

    # Get vector passages
    chunks = vector_retrieve(query, top_k=8)

    # Group by city for structured context
    by_city = {}
    for c in chunks:
        meta = c.get("metadata", {})
        city = meta.get("city", "unknown")
        by_city.setdefault(city, []).append(c.get("content", ""))

    vector_ctx = "\n\n".join(
        f"=== {city} ===\n" + "\n".join(texts[:3])
        for city, texts in by_city.items()
    )

    # Count sources for display
    source_cities = list(by_city.keys())
    source_count = len(chunks)

    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=OPENAI_KEY)

    system_prompt = (
        "You are GT CURA's Policy Intelligence assistant -- an expert on building code "
        "amendments across US cities. You help developers, city planners, and investors "
        "understand how building codes differ across jurisdictions.\n\n"
        "RULES:\n"
        "1. Always cite specific code sections, ordinance numbers, and document sources\n"
        "2. When comparing cities, use clear structure (city-by-city or table format)\n"
        "3. Highlight climate resilience provisions (wildfire, seismic, flood, heat)\n"
        "4. Note which base code each city uses (CBC vs IBC)\n"
        "5. If information is not available, say so -- never fabricate\n"
        "6. End with a brief 'Key Takeaway' for decision-makers\n"
    )

    context = ""
    if graph_ctx:
        context += f"KNOWLEDGE GRAPH DATA:\n{graph_ctx}\n\n"
    context += f"RETRIEVED PASSAGES ({source_count} from {len(source_cities)} cities):\n{vector_ctx}"

    response = llm.invoke(
        f"{system_prompt}\n\nCONTEXT:\n{context}\n\nQUESTION: {query}"
    )

    return response.content, source_cities, source_count

# ─── Chat Interface ───────────────────────────────────────────────────────────

# Initialize chat history
if "policy_messages" not in st.session_state:
    st.session_state.policy_messages = []

# Display chat history
for msg in st.session_state.policy_messages:
    if isinstance(msg, dict):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                st.caption(f"Sources: {msg['sources']}")

# Handle preset or typed input
user_input = st.chat_input("Ask about building code amendments across cities...")

if selected_preset:
    user_input = selected_preset

if user_input:
    # Show user message
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.policy_messages.append({"role": "user", "content": user_input})

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Searching 12,000+ code passages across 8 cities..."):
            t0 = time.time()
            answer, source_cities, source_count = generate_answer(user_input)
            elapsed = time.time() - t0

        st.markdown(answer)
        source_text = f"{source_count} passages from {', '.join(source_cities)} ({elapsed:.1f}s)"
        st.caption(f"Sources: {source_text}")

    st.session_state.policy_messages.append({
        "role": "assistant",
        "content": answer,
        "sources": source_text,
    })
