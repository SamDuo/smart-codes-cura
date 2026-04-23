### IMPORT DEPENDENCIES ###

import logging
import os
import sys
import time

import streamlit as st
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import httpx

logger = logging.getLogger(__name__)

# Add parent directory so we can import multi_agent_rag
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

### SET UP STREAMLIT APP ###

st.set_page_config(page_title="Agentic RAG Chatbot", page_icon="🤖", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 2rem; max-width: 1200px; }
    .agent-badge {
        display: inline-block;
        background: #eef1f8;
        color: #667eea;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .example-chip button {
        background: #f5f7fb !important;
        border: 1px solid #e2e6ee !important;
        color: #4a5568 !important;
        font-size: 0.88rem !important;
        border-radius: 20px !important;
        padding: 6px 14px !important;
    }
    .example-chip button:hover {
        border-color: #667eea !important;
        color: #667eea !important;
        background: #eef1f8 !important;
    }
</style>
""", unsafe_allow_html=True)

### LOAD CONFIG ###


def get_secret(name):
    if name in st.secrets:
        return st.secrets[name]
    st.error(f"Missing required secret: {name}")
    st.stop()


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_SERVICE_KEY = get_secret("SUPABASE_SERVICE_KEY")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")

SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
}

# Validate Supabase connection
try:
    _check = httpx.get(
        f"{SUPABASE_URL}/rest/v1/documents?select=id&limit=1",
        headers=SUPABASE_HEADERS,
        timeout=10,
    )
    if _check.status_code == 401:
        st.error("Supabase authentication failed. Update SUPABASE_SERVICE_KEY.")
        st.stop()
    elif _check.status_code != 200:
        st.error(f"Supabase error ({_check.status_code})")
        st.stop()
except httpx.ConnectError:
    st.error("Cannot connect to Supabase.")
    st.stop()

embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=OPENAI_API_KEY)


### RETRIEVAL MODES ###


BASELINE_MIN_SIMILARITY = 0.4  # Match multi-agent threshold for fair comparison
BASELINE_NAN = (
    "I don't have sufficient information in our building code database "
    "to answer this question."
)


def baseline_answer(question: str) -> str:
    """Baseline: simple vector search + single LLM call.

    Uses the same similarity threshold as multi-agent so evaluation comparisons
    are apples-to-apples.
    """
    query_embedding = embeddings.embed_query(question)

    res = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/match_documents",
        headers=SUPABASE_HEADERS,
        json={"query_embedding": query_embedding, "match_count": 5},
        timeout=30,
    )
    chunks = res.json() if res.status_code == 200 else []
    chunks = [c for c in chunks if c.get("similarity", 0) >= BASELINE_MIN_SIMILARITY]

    if not chunks:
        return BASELINE_NAN

    context = "\n\n".join(
        f"Source: {c.get('metadata', {}).get('original_filename', 'unknown')} "
        f"(City: {c.get('metadata', {}).get('city', 'unknown')})\n"
        f"Content: {c.get('content', '')}"
        for c in chunks
    )

    llm = ChatOpenAI(
        model="gpt-4o", temperature=0, api_key=OPENAI_API_KEY, request_timeout=30
    )
    response = llm.invoke(
        f"Based on the following building code documents, answer the question. "
        f"Cite specific code sections and source documents. "
        f"If the information is not available, say so clearly.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )
    return response.content


def stream_multi_agent(question: str):
    """Streaming multi-agent pipeline -- yields tokens, captures metadata."""
    from multi_agent_rag import stream_multi_agent_answer
    for chunk in stream_multi_agent_answer(question):
        if isinstance(chunk, dict) and "_meta" in chunk:
            # Store metadata in session state for display after streaming
            st.session_state["_last_meta"] = chunk["_meta"]
        else:
            yield chunk


### SIDEBAR ###

with st.sidebar:
    st.markdown("### Settings")

    mode = st.radio(
        "Retrieval mode",
        ["Multi-Agent RAG", "Baseline (Vector-Only)"],
        index=0,
        help="Multi-Agent uses specialist agents for different question types. "
             "Baseline uses simple vector search.",
    )

    if st.button("Clear chat history", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    with st.expander("Active pipeline", expanded=True):
        if mode == "Multi-Agent RAG":
            st.markdown(
                "**Agents**\n"
                "- Classifier (gpt-4o-mini)\n"
                "- Factual · Cross-Jurisdiction\n"
                "- Temporal · Compliance\n"
                "- Citation Validator\n\n"
                "**Data**\n"
                "- Supabase pgvector (12,280 chunks)\n"
                "- Neo4j knowledge graph"
            )
        else:
            st.markdown(
                "**Pipeline**\n"
                "Vector search (top-5) → GPT-4o\n\n"
                "**Data**\n"
                "- Supabase pgvector (12,280 chunks)"
            )

    st.caption("Powered by GT CURA")

### MAIN LAYOUT ###

col1, col2 = st.columns([1, 5])

with col1:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(app_dir, "..", "gt_cura_logo.jpg")
    if os.path.exists(logo_path):
        st.image(logo_path, width=90)

with col2:
    st.header("Building Code Chatbot")
    mode_label = "Multi-Agent RAG" if mode == "Multi-Agent RAG" else "Baseline"
    st.caption(f"Mode: {mode_label}  ·  10 cities  ·  12,280 indexed passages")

### CHAT ###

if "messages" not in st.session_state:
    st.session_state.messages = []

EXAMPLE_QUERIES = [
    "How do LA and Phoenix differ on fire protection?",
    "What seismic requirements apply in California vs Nevada?",
    "Which cities have the most recent code adoptions?",
    "What are Atlanta's stormwater amendments?",
]

# Show example chips only when chat is empty
if not st.session_state.messages:
    st.markdown("##### Try an example")
    chip_cols = st.columns(len(EXAMPLE_QUERIES))
    for i, (col, q) in enumerate(zip(chip_cols, EXAMPLE_QUERIES)):
        with col:
            with st.container():
                st.markdown('<div class="example-chip">', unsafe_allow_html=True)
                if st.button(q, key=f"ex_{i}", use_container_width=True):
                    st.session_state["_preset_query"] = q
                st.markdown('</div>', unsafe_allow_html=True)

for message in st.session_state.messages:
    if isinstance(message, dict):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("meta"):
                st.caption(message["meta"])

user_question = st.chat_input("Ask about building codes across U.S. cities...")

# Preset from example chip
if not user_question and st.session_state.get("_preset_query"):
    user_question = st.session_state.pop("_preset_query")

if user_question:
    st.session_state.messages.append({"role": "user", "content": user_question})
    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        t0 = time.time()
        st.session_state["_last_meta"] = {}
        try:
            if mode == "Multi-Agent RAG":
                answer = st.write_stream(stream_multi_agent(user_question))
            else:
                with st.spinner("Searching knowledge base..."):
                    answer = baseline_answer(user_question)
                st.markdown(answer)
            elapsed = time.time() - t0
            last_meta = st.session_state.get("_last_meta", {})
            cached = last_meta.get("cached", False)
            agent_type = last_meta.get("agent", "")
            validation = last_meta.get("validation")
            cache_tag = " | cached" if cached else ""
            agent_tag = f" | {agent_type}" if agent_type else ""
            meta = f"{mode_label}{agent_tag} | {elapsed:.1f}s{cache_tag}"
            if validation:
                st.warning(f"Validator flagged: {validation}")
        except Exception:
            logger.exception("Chatbot answer generation failed")
            answer = (
                "Sorry, something went wrong while generating the answer. "
                "Please try again or rephrase your question."
            )
            meta = f"{mode_label} | error"
            st.markdown(answer)

        st.caption(meta)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "meta": meta,
    })
