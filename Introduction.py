import os
import streamlit as st

st.set_page_config(
    page_title="GT CURA | Smart Codes",
    page_icon="🏙️",
    layout="wide",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .hero-title {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .hero-subtitle {
        font-size: 1.3rem;
        color: #6c757d;
        margin-top: -5px;
    }
    .feature-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 24px;
        border-left: 4px solid #667eea;
        margin-bottom: 12px;
    }
    .stat-big {
        font-size: 2.5rem;
        font-weight: 700;
        color: #667eea;
    }
</style>
""", unsafe_allow_html=True)

# ─── Header ──────────────────────────────────────────────────────────────────

col1, col2 = st.columns([1, 5])
with col1:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(app_dir, "gt_cura_logo.jpg")
    if os.path.exists(logo_path):
        st.image(logo_path, width=100)

with col2:
    st.markdown('<p class="hero-title">GT CURA Smart Codes</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-subtitle">Building Code Amendment Intelligence for Resilient Cities</p>', unsafe_allow_html=True)

st.divider()

# ─── Value Prop ───────────────────────────────────────────────────────────────

st.markdown("""
### The Problem

Cities spend **billions** on resilience with no AI tools to compare building code amendments across jurisdictions.
A developer expanding from Phoenix to LA has no way to instantly understand how fire codes differ.
An insurance underwriter can't quantify whether a city's code recency affects risk.
GIS consulting costs **$200K+** per project and delivers static reports.

### The Solution

**GT CURA Policy Intelligence** is a hybrid RAG system that combines knowledge graph structure
with vector search to deliver cross-jurisdiction building code amendment analysis in seconds.
""")

# ─── Stats ────────────────────────────────────────────────────────────────────

st.divider()

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown('<p class="stat-big">8</p>', unsafe_allow_html=True)
    st.caption("Cities covered")
with c2:
    st.markdown('<p class="stat-big">41</p>', unsafe_allow_html=True)
    st.caption("Amendment documents")
with c3:
    st.markdown('<p class="stat-big">12K+</p>', unsafe_allow_html=True)
    st.caption("Indexed passages")
with c4:
    st.markdown('<p class="stat-big">16 yrs</p>', unsafe_allow_html=True)
    st.caption("Time span (2010-2026)")

st.divider()

# ─── Features ─────────────────────────────────────────────────────────────────

st.markdown("### Capabilities")

f1, f2, f3 = st.columns(3)

with f1:
    st.markdown("""
    **Cross-Jurisdiction Comparison**

    Compare fire, seismic, energy, and accessibility
    amendments across cities instantly. Understand how
    California (CBC) cities differ from Nevada/Arizona (IBC) cities.
    """)

with f2:
    st.markdown("""
    **Climate Resilience Analysis**

    Identify which cities have adopted amendments for
    wildfire, earthquake, extreme heat, and flood hazards.
    Track amendment recency to assess code currency.
    """)

with f3:
    st.markdown("""
    **Amendment Intelligence**

    Search 12,000+ indexed passages with AI that
    understands code structure, section references,
    and amendment relationships across jurisdictions.
    """)

st.divider()

# ─── Navigation ───────────────────────────────────────────────────────────────

st.markdown("### Get Started")
st.markdown("""
- **Policy Intelligence** -- Ask questions about building code amendments across 8 cities
- **Knowledge Base** -- Upload and manage building code documents
- **Chatbot** -- General-purpose Q&A on ingested documents
""")

st.divider()

# ─── Footer ───────────────────────────────────────────────────────────────────

st.caption("Powered by GT CURA")
