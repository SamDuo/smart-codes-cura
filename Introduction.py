import os
import streamlit as st

st.set_page_config(
    page_title="GT CURA | Smart Codes",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .block-container { padding-top: 2rem; max-width: 1200px; }

    .hero-title {
        font-size: 3.2rem;
        font-weight: 800;
        line-height: 1.1;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .hero-subtitle {
        font-size: 1.25rem;
        color: #6c757d;
        margin-top: 4px;
        font-weight: 400;
    }

    .stat-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #eef1f8 100%);
        border-radius: 14px;
        padding: 20px 16px;
        text-align: center;
        border: 1px solid #e2e6ee;
        transition: transform 0.15s, box-shadow 0.15s;
    }
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.12);
    }
    .stat-big {
        font-size: 2.4rem;
        font-weight: 700;
        color: #667eea;
        line-height: 1;
        margin: 0;
    }
    .stat-label {
        font-size: 0.8rem;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 6px;
    }

    .feature-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 24px;
        border: 1px solid #e2e6ee;
        height: 100%;
        transition: border-color 0.15s, box-shadow 0.15s;
    }
    .feature-card:hover {
        border-color: #667eea;
        box-shadow: 0 6px 18px rgba(102, 126, 234, 0.12);
    }
    .feature-icon {
        font-size: 1.6rem;
        margin-bottom: 8px;
    }
    .feature-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 6px;
    }
    .feature-body {
        font-size: 0.92rem;
        color: #4a5568;
        line-height: 1.5;
    }

    .nav-pill {
        display: inline-block;
        background: #eef1f8;
        color: #667eea;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-right: 8px;
    }

    hr { margin: 2rem 0; }
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
    st.markdown(
        '<p class="hero-subtitle">Building Code Amendment Intelligence for Resilient Cities</p>',
        unsafe_allow_html=True,
    )

st.divider()

# ─── Value Prop ──────────────────────────────────────────────────────────────

st.markdown("### Why this matters")
st.markdown(
    "Cities spend **billions** on resilience with no AI tools to compare building code "
    "amendments across jurisdictions. A developer expanding from Phoenix to LA has no "
    "way to instantly understand how fire codes differ. An insurance underwriter can't "
    "quantify whether a city's code recency affects risk. GIS consulting costs **$200K+** "
    "per project and delivers static reports."
)
st.markdown(
    "**Smart Codes** combines a knowledge graph with retrieval-augmented generation "
    "to deliver cross-jurisdiction amendment analysis in seconds — not weeks."
)

st.divider()

# ─── Stats ───────────────────────────────────────────────────────────────────

stats = [
    ("10", "Cities covered"),
    ("50+", "Amendment documents"),
    ("12K+", "Indexed passages"),
    ("16 yrs", "Time span (2010 – 2026)"),
]
cols = st.columns(len(stats))
for col, (value, label) in zip(cols, stats):
    with col:
        st.markdown(
            f'<div class="stat-card">'
            f'<p class="stat-big">{value}</p>'
            f'<p class="stat-label">{label}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.divider()

# ─── Features ────────────────────────────────────────────────────────────────

st.markdown("### Capabilities")

features = [
    (
        "🔀",
        "Cross-jurisdiction comparison",
        "Compare fire, seismic, energy, and accessibility amendments across cities "
        "instantly. Understand how California (CBC) cities differ from Nevada, "
        "Arizona, and Georgia (IBC) cities.",
    ),
    (
        "🌡️",
        "Climate resilience analysis",
        "Identify which cities have adopted amendments for wildfire, earthquake, "
        "extreme heat, and flood hazards. Track amendment recency to assess code currency.",
    ),
    (
        "📚",
        "Amendment intelligence",
        "Search 12,000+ indexed passages with multi-agent AI that understands code "
        "structure, section references, and amendment relationships across jurisdictions.",
    ),
]
cols = st.columns(len(features))
for col, (icon, title, body) in zip(cols, features):
    with col:
        st.markdown(
            f'<div class="feature-card">'
            f'<div class="feature-icon">{icon}</div>'
            f'<div class="feature-title">{title}</div>'
            f'<div class="feature-body">{body}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.divider()

# ─── Navigation ──────────────────────────────────────────────────────────────

st.markdown("### Explore the platform")
nav_cols = st.columns(3)

nav_items = [
    (
        "🤖",
        "Chatbot",
        "Ask natural-language questions about building codes across all 10 cities. "
        "Routes to specialist agents (factual, cross-jurisdiction, temporal, compliance).",
        "Multi-agent RAG",
    ),
    (
        "🏙️",
        "Policy Intelligence",
        "Interactive dashboard with charts, adoption timelines, and side-by-side "
        "city comparisons. Built-in preset queries for common analyses.",
        "Analytics",
    ),
    (
        "🗺️",
        "Map Intelligence",
        "Geographic view of 11 building zones across 4 states. Click any zone to "
        "see its base code, hazards, and key amendments.",
        "Geospatial",
    ),
]
for col, (icon, title, body, tag) in zip(nav_cols, nav_items):
    with col:
        st.markdown(
            f'<div class="feature-card">'
            f'<div class="feature-icon">{icon}</div>'
            f'<div class="feature-title">{title}</div>'
            f'<span class="nav-pill">{tag}</span>'
            f'<div class="feature-body" style="margin-top:10px">{body}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.divider()

# ─── Footer ──────────────────────────────────────────────────────────────────

st.caption("Powered by GT CURA  |  Georgia Tech Center for Urban Resilience and Analytics")
