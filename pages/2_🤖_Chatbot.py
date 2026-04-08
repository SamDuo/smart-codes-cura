### IMPORT DEPENDENCIES ###

import os
import sys
import time

import streamlit as st
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import httpx

# Add parent directory so we can import multi_agent_rag
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

### SET UP STREAMLIT APP ###

st.set_page_config(page_title="Agentic RAG Chatbot", page_icon="🤖", layout="wide")

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


def baseline_answer(question: str) -> str:
    """Baseline: simple vector search + single LLM call."""
    query_embedding = embeddings.embed_query(question)

    res = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/match_documents",
        headers=SUPABASE_HEADERS,
        json={"query_embedding": query_embedding, "match_count": 5},
        timeout=30,
    )
    chunks = res.json() if res.status_code == 200 else []

    context = "\n\n".join(
        f"Source: {c.get('metadata', {}).get('original_filename', 'unknown')} "
        f"(City: {c.get('metadata', {}).get('city', 'unknown')})\n"
        f"Content: {c.get('content', '')}"
        for c in chunks
    )

    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=OPENAI_API_KEY)
    response = llm.invoke(
        f"Based on the following building code documents, answer the question. "
        f"Cite specific code sections and source documents. "
        f"If the information is not available, say so clearly.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )
    return response.content


def stream_multi_agent(question: str):
    """Streaming multi-agent pipeline -- yields tokens as they generate."""
    from multi_agent_rag import stream_multi_agent_answer
    yield from stream_multi_agent_answer(question)


### SIDEBAR ###

with st.sidebar:
    st.title("Settings")

    mode = st.radio(
        "Retrieval Mode",
        ["Multi-Agent RAG", "Baseline (Vector-Only)"],
        index=0,
        help="Multi-Agent uses specialist agents for different question types. "
             "Baseline uses simple vector search.",
    )

    st.divider()

    if mode == "Multi-Agent RAG":
        st.markdown("**Active Agents:**")
        st.markdown(
            "- Classifier (GPT-4o-mini)\n"
            "- Factual Agent\n"
            "- Cross-Jurisdiction Agent\n"
            "- Temporal Agent\n"
            "- Compliance Agent\n"
            "- Citation Validator"
        )
        st.markdown("**Data Sources:**")
        st.markdown("- Supabase pgvector (12,280 chunks)\n- Neo4j Knowledge Graph")
    else:
        st.markdown("**Pipeline:**")
        st.markdown("Vector search (top-5) -> GPT-4o")
        st.markdown("**Data Source:**")
        st.markdown("- Supabase pgvector (12,280 chunks)")

    st.divider()
    st.caption("Powered by GT CURA")

### MAIN LAYOUT ###

col1, col2 = st.columns([1, 5])

with col1:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(app_dir, "..", "gt_cura_logo.jpg")
    if os.path.exists(logo_path):
        st.image(logo_path)

with col2:
    st.header("Building Code Chatbot")
    mode_label = "Multi-Agent RAG" if mode == "Multi-Agent RAG" else "Baseline"
    st.caption(f"Mode: {mode_label} | 9 cities | 12,280 passages")

### CHAT ###

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    if isinstance(message, dict):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("meta"):
                st.caption(message["meta"])

user_question = st.chat_input("Ask about building codes across U.S. cities...")

if user_question:
    st.session_state.messages.append({"role": "user", "content": user_question})
    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        t0 = time.time()
        try:
            if mode == "Multi-Agent RAG":
                # Streaming: tokens appear as they generate
                answer = st.write_stream(stream_multi_agent(user_question))
            else:
                with st.spinner("Searching knowledge base..."):
                    answer = baseline_answer(user_question)
                st.markdown(answer)
            elapsed = time.time() - t0
            meta = f"{mode_label} | {elapsed:.1f}s"
        except Exception as e:
            answer = f"Error: {e}"
            meta = f"{mode_label} | error"
            st.markdown(answer)

        st.caption(meta)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "meta": meta,
    })
