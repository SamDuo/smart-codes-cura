"""
LightRAG Hybrid Retriever for SmartCodes
==========================================

Provides knowledge-graph-augmented retrieval over building code documents
using LightRAG (hybrid KG + vector search).

Modes:
  - naive:  Simple vector similarity (baseline)
  - local:  Entity-centric subgraph retrieval
  - global: Community-level summarisation
  - hybrid: Combines local + global (recommended for building codes)
  - mix:    Combines naive + local + global (most comprehensive)

Usage as a module:
  from lightrag_retriever import lightrag_query, index_documents
  answer = lightrag_query("What fire-resistance rating is required?", mode="hybrid")

Usage from CLI:
  python lightrag_retriever.py index ./data/parsed
  python lightrag_retriever.py query "What amendments does LA have for Chapter 7?"
"""

import os
import sys
import glob

# ─── LightRAG Import (with fallback) ───────────────────────────────────────

USE_LIGHTRAG = False
LIGHTRAG_ERROR = ""

try:
    from lightrag import LightRAG, QueryParam
    from lightrag.llm.openai import openai_complete_if_cache, openai_embed
    from lightrag.utils import EmbeddingFunc

    USE_LIGHTRAG = True
except Exception as e:
    LIGHTRAG_ERROR = str(e)

# ─── Configuration ──────────────────────────────────────────────────────────

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# Directory for the LightRAG index (knowledge graph + vector store)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.path.join(SCRIPT_DIR, "lightrag_index")

# Set OpenAI key in environment (required by LightRAG internals)
os.environ.setdefault("OPENAI_API_KEY", OPENAI_KEY)

# ─── LightRAG Instance ─────────────────────────────────────────────────────

_rag_instance = None

VALID_MODES = {"naive", "local", "global", "hybrid", "mix"}


def get_rag() -> "LightRAG":
    """Get or create the singleton LightRAG instance."""
    global _rag_instance
    if _rag_instance is not None:
        return _rag_instance

    if not USE_LIGHTRAG:
        raise RuntimeError(
            f"LightRAG is not available: {LIGHTRAG_ERROR}\n"
            f"Install with: pip install lightrag-hku"
        )

    os.makedirs(INDEX_DIR, exist_ok=True)

    import asyncio

    _rag_instance = LightRAG(
        working_dir=INDEX_DIR,
        llm_model_func=openai_complete_if_cache,
        llm_model_name="gpt-4o-mini",       # cheaper model for KG extraction
        llm_model_max_async=4,               # parallel extraction calls
        embedding_func=EmbeddingFunc(
            embedding_dim=3072,              # text-embedding-3-large dimension
            max_token_size=8192,
            func=lambda texts: openai_embed(
                texts, model="text-embedding-3-large"
            ),
        ),
    )

    # LightRAG v1.4+ requires async initialization
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside an already-running loop (e.g. Streamlit)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _rag_instance.initialize_storages()).result()
        else:
            loop.run_until_complete(_rag_instance.initialize_storages())
    except RuntimeError:
        asyncio.run(_rag_instance.initialize_storages())

    return _rag_instance


# ─── Indexing Functions ─────────────────────────────────────────────────────


def index_documents(source_dir: str) -> dict:
    """Index all .md and .txt files from a directory into LightRAG.

    This extracts entities and relations (building codes, sections,
    jurisdictions, requirements) and builds the knowledge graph.

    Args:
        source_dir: Directory containing Markdown or text files
                    (e.g., output from ingest_docling.py's Markdown export).

    Returns:
        Dict with indexing stats.
    """
    rag = get_rag()

    # Gather all text/markdown files
    patterns = ["*.md", "*.txt"]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(source_dir, pattern)))
    files.sort()

    if not files:
        print(f"No .md or .txt files found in {source_dir}")
        return {"files": 0, "indexed": 0}

    print(f"Found {len(files)} documents to index into LightRAG")
    indexed = 0

    for filepath in files:
        filename = os.path.basename(filepath)
        print(f"  Indexing: {filename}")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                print(f"    Skipped (empty)")
                continue
            rag.insert(content, file_paths=[filepath])
            indexed += 1
            print(f"    Done ({len(content):,} chars)")
        except Exception as e:
            print(f"    ERROR: {e}")

    stats = {"files": len(files), "indexed": indexed, "index_dir": INDEX_DIR}
    print(f"\nIndexing complete: {indexed}/{len(files)} files")
    print(f"Index stored at: {INDEX_DIR}")
    return stats


def index_from_supabase(limit: int = 500) -> dict:
    """Pull documents from Supabase and index them into LightRAG.

    Useful when the parsed Markdown files are not available locally
    but the data is already in the Supabase vector store.
    """
    import httpx

    rag = get_rag()

    print("Fetching documents from Supabase...")
    res = httpx.get(
        f"{SUPABASE_URL}/rest/v1/documents",
        headers=SUPABASE_HEADERS,
        params={"select": "content,metadata", "limit": str(limit)},
        timeout=60,
    )

    if res.status_code != 200:
        print(f"Error fetching from Supabase: {res.status_code} - {res.text[:200]}")
        return {"error": res.text[:200]}

    rows = res.json()
    print(f"Fetched {len(rows)} document chunks from Supabase")

    if not rows:
        return {"files": 0, "indexed": 0}

    # Group chunks by source file for better KG extraction
    by_file: dict[str, list[str]] = {}
    for row in rows:
        meta = row.get("metadata", {})
        source = meta.get("original_filename", "unknown")
        content = row.get("content", "")
        if content.strip():
            by_file.setdefault(source, []).append(content)

    indexed = 0
    for source_file, chunks in by_file.items():
        print(f"  Indexing: {source_file} ({len(chunks)} chunks)")
        try:
            combined = "\n\n".join(chunks)
            rag.insert(combined, file_paths=[source_file])
            indexed += 1
        except Exception as e:
            print(f"    ERROR: {e}")

    stats = {
        "supabase_rows": len(rows),
        "source_files": len(by_file),
        "indexed": indexed,
    }
    print(f"\nIndexed {indexed}/{len(by_file)} source files from Supabase")
    return stats


# ─── Retrieval Functions ────────────────────────────────────────────────────


def lightrag_query(
    question: str,
    mode: str = "hybrid",
    top_k: int = 40,
    stream: bool = False,
) -> str:
    """Query the LightRAG knowledge graph.

    This is the main function for the Streamlit chatbot to call.

    Args:
        question: The user's question about building codes.
        mode: Retrieval mode. One of:
            - "naive":  Pure vector similarity (fast, simple)
            - "local":  Entity-neighbourhood subgraph (good for specific codes)
            - "global": Community-level summaries (good for overview questions)
            - "hybrid": local + global (recommended default)
            - "mix":    naive + local + global (most comprehensive)
        top_k: Number of top results to retrieve.
        stream: Whether to stream the response.

    Returns:
        The answer string from LightRAG.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Choose from: {VALID_MODES}")

    rag = get_rag()

    param = QueryParam(
        mode=mode,
        top_k=top_k,
        stream=stream,
    )

    result = rag.query(question, param=param)
    return result


def lightrag_query_naive(question: str, **kwargs) -> str:
    """Pure vector similarity search (baseline)."""
    return lightrag_query(question, mode="naive", **kwargs)


def lightrag_query_local(question: str, **kwargs) -> str:
    """Entity-centric subgraph retrieval.
    Good for: 'What does Section 1613 require?'
    """
    return lightrag_query(question, mode="local", **kwargs)


def lightrag_query_global(question: str, **kwargs) -> str:
    """Community-level summarisation retrieval.
    Good for: 'How do fire codes differ across jurisdictions?'
    """
    return lightrag_query(question, mode="global", **kwargs)


def lightrag_query_hybrid(question: str, **kwargs) -> str:
    """Combined local + global retrieval (recommended).
    Good for: 'What amendments does Los Angeles have for seismic design?'
    """
    return lightrag_query(question, mode="hybrid", **kwargs)


def lightrag_query_mix(question: str, **kwargs) -> str:
    """Most comprehensive: naive + local + global.
    Good for: complex cross-jurisdictional comparisons.
    """
    return lightrag_query(question, mode="mix", **kwargs)


# ─── Graph Inspection Utilities ─────────────────────────────────────────────


def get_graph_stats() -> dict:
    """Return basic stats about the knowledge graph."""
    rag = get_rag()
    try:
        labels = rag.get_graph_labels()
        return {"labels": labels, "index_dir": INDEX_DIR}
    except Exception as e:
        return {"error": str(e), "index_dir": INDEX_DIR}


def get_entity_info(entity_name: str) -> dict:
    """Look up a specific entity in the knowledge graph."""
    rag = get_rag()
    try:
        info = rag.get_entity_info(entity_name)
        return info if info else {"message": f"Entity '{entity_name}' not found"}
    except Exception as e:
        return {"error": str(e)}


# ─── Streamlit Integration Helper ──────────────────────────────────────────


def create_lightrag_tool():
    """Create a LangChain-compatible tool for the Streamlit chatbot.

    Usage in the chatbot page:
        from lightrag_retriever import create_lightrag_tool
        tools = [retrieve, create_lightrag_tool()]
    """
    from langchain_core.tools import tool as lc_tool

    @lc_tool(response_format="content_and_artifact")
    def lightrag_search(query: str):
        """Search building codes using knowledge graph retrieval.
        Uses hybrid mode combining entity relationships and community summaries
        for comprehensive answers about building code amendments.
        """
        try:
            answer = lightrag_query(query, mode="hybrid")
            return answer, [{"source": "lightrag", "mode": "hybrid", "query": query}]
        except Exception as e:
            fallback = f"LightRAG search failed: {e}. Please use the standard retriever."
            return fallback, []

    return lightrag_search


# ─── CLI ────────────────────────────────────────────────────────────────────

def print_usage():
    print("Usage:")
    print("  python lightrag_retriever.py index <directory>")
    print("  python lightrag_retriever.py index-supabase [limit]")
    print("  python lightrag_retriever.py query <question> [mode]")
    print("  python lightrag_retriever.py stats")
    print("")
    print("Modes: naive, local, global, hybrid (default), mix")
    print("")
    print("Examples:")
    print("  python lightrag_retriever.py index ./data/parsed")
    print("  python lightrag_retriever.py index-supabase 200")
    print("  python lightrag_retriever.py query 'What fire rating is required for Chapter 7?' hybrid")
    print("  python lightrag_retriever.py stats")
    print("")
    print(f"LightRAG available: {USE_LIGHTRAG}")
    if not USE_LIGHTRAG:
        print(f"Error: {LIGHTRAG_ERROR}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "index":
        if len(sys.argv) < 3:
            print("Error: provide directory path")
            print_usage()
            sys.exit(1)
        source_dir = sys.argv[2]
        stats = index_documents(source_dir)
        print(f"\nResult: {stats}")

    elif command == "index-supabase":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 500
        stats = index_from_supabase(limit=limit)
        print(f"\nResult: {stats}")

    elif command == "query":
        if len(sys.argv) < 3:
            print("Error: provide a question")
            print_usage()
            sys.exit(1)
        question = sys.argv[2]
        mode = sys.argv[3] if len(sys.argv) > 3 else "hybrid"
        print(f"\nQuery: {question}")
        print(f"Mode:  {mode}")
        print(f"{'=' * 60}")
        answer = lightrag_query(question, mode=mode)
        print(answer)

    elif command == "stats":
        stats = get_graph_stats()
        print(f"Graph stats: {stats}")

    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)
