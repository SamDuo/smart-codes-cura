"""
GT CURA Map Intelligence
============================
Map-based building code + zoning intelligence for California cities.
Click on a zone to see applicable codes, hazards, and amendments.
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import httpx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

st.set_page_config(
    page_title="GT CURA | Map Intelligence",
    page_icon="🗺️",
    layout="wide",
)

# ─── Secrets ──────────────────────────────────────────────────────────────────

def get_secret(name):
    if name in st.secrets:
        return st.secrets[name]
    return ""

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_SERVICE_KEY")
OPENAI_KEY = get_secret("OPENAI_API_KEY")
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .zone-header { font-size: 1.4rem; font-weight: 700; color: #1a1a2e; }
    .hazard-tag {
        display: inline-block; padding: 4px 10px; border-radius: 12px;
        font-size: 0.75rem; font-weight: 600; margin: 2px;
    }
    .hazard-fire { background: #fce4ec; color: #c62828; }
    .hazard-seismic { background: #f3e5f5; color: #6a1b9a; }
    .hazard-flood { background: #e3f2fd; color: #1565c0; }
    .hazard-heat { background: #fff3e0; color: #e65100; }
    .hazard-wildfire { background: #fff8e1; color: #ff6f00; }
    .code-stat { font-size: 1.8rem; font-weight: 700; color: #667eea; }
</style>
""", unsafe_allow_html=True)

# ─── California Zones ───────────────────────────────────────────────────────

CALIFORNIA_ZONES = [
    {
        "name": "Downtown Los Angeles",
        "lat": 34.0407, "lon": -118.2468,
        "city": "Los Angeles",
        "zoning": "C2 (Commercial Zone)",
        "max_height": "No limit (with FAR bonus)",
        "far": "6.0 - 13.0",
        "code_edition": "2019 CBC (LA Amendments)",
        "hazards": ["Seismic (Zone D)", "Wildfire (VHFHSZ nearby)"],
        "climate_provisions": "LA Green Building Code, Cool roof requirements, EV charging mandates",
        "key_amendments": "Chapters 16A (Seismic), 7A (Wildfire), 88-96 (Earthquake Hazard Reduction)",
        "color": "#e74c3c",
    },
    {
        "name": "Hollywood / Wilshire",
        "lat": 34.0928, "lon": -118.3287,
        "city": "Los Angeles",
        "zoning": "C4 (Commercial Zone)",
        "max_height": "Varies by specific plan",
        "far": "3.0 - 6.0",
        "code_edition": "2019 CBC (LA Amendments)",
        "hazards": ["Seismic (Zone D)", "Wildfire (hillside areas)"],
        "climate_provisions": "Hillside ordinance, Seismic retrofit requirements for soft-story buildings",
        "key_amendments": "Chapter 91 (Tilt-Up Concrete), Chapter 93 (Wood-Frame Retrofit)",
        "color": "#c0392b",
    },
    {
        "name": "Downtown San Diego",
        "lat": 32.7157, "lon": -117.1611,
        "city": "San Diego",
        "zoning": "CCPD (Centre City Planned District)",
        "max_height": "Up to 500 ft (varies by block)",
        "far": "10.0 - 20.0",
        "code_edition": "2025 CBC (SD Amendments)",
        "hazards": ["Seismic", "Coastal Flood", "Wildfire (eastern interface)"],
        "climate_provisions": "Climate Action Plan, Zero-net-energy by 2030, EV-ready requirements",
        "key_amendments": "SD Municipal Code Ch 14 Art 5, Construction/demolition amendments",
        "color": "#3498db",
    },
    {
        "name": "La Jolla / UC San Diego",
        "lat": 32.8328, "lon": -117.2713,
        "city": "San Diego",
        "zoning": "RS-1-7 / CN-1-2 (Residential / Commercial)",
        "max_height": "30 ft (coastal overlay)",
        "far": "0.60 - 1.50",
        "code_edition": "2025 CBC (SD Amendments)",
        "hazards": ["Coastal Erosion", "Seismic", "Wildfire (Torrey Pines)"],
        "climate_provisions": "Coastal overlay zone, Bluff setback requirements, Sea level rise adaptation",
        "key_amendments": "Environmentally Sensitive Lands regulations, Coastal development permits",
        "color": "#2980b9",
    },
    {
        "name": "Irvine Business Complex",
        "lat": 33.6846, "lon": -117.8265,
        "city": "Irvine",
        "zoning": "Multi-Use (Irvine Business Complex)",
        "max_height": "Up to 400 ft (with approval)",
        "far": "Varies by master plan",
        "code_edition": "2025 CBC (Irvine Amendments)",
        "hazards": ["Seismic", "Wildfire (eastern foothills)"],
        "climate_provisions": "CalGreen Tier 1 mandatory, EV charging for new construction",
        "key_amendments": "Irvine Municipal Code Division 9, Swimming pool construction code, Fire code amendments",
        "color": "#2ecc71",
    },
    {
        "name": "Santa Clarita / Valencia",
        "lat": 34.3917, "lon": -118.5426,
        "city": "Santa Clarita",
        "zoning": "CC (Community Commercial)",
        "max_height": "50 ft",
        "far": "1.0 - 2.0",
        "code_edition": "2025 CBC (Santa Clarita Amendments)",
        "hazards": ["Wildfire (VHFHSZ)", "Seismic (San Andreas proximity)"],
        "climate_provisions": "Wildland-urban interface requirements, Defensible space mandates",
        "key_amendments": "Energy Conservation Code, Fire Code amendments, Residential sprinkler requirements",
        "color": "#f39c12",
    },
]

# ─── Header ──────────────────────────────────────────────────────────────────

st.markdown("## 🗺️ GT CURA Map Intelligence — California")
st.markdown("*Click on any zone to see building code requirements, hazard exposure, and amendments*")

# ─── Layout: Map + Details ────────────────────────────────────────────────────

col_map, col_detail = st.columns([3, 2])

with col_map:
    m = folium.Map(
        location=[34.0, -118.0],
        zoom_start=8,
        tiles="CartoDB positron",
    )

    for zone in CALIFORNIA_ZONES:
        popup_html = f"""
        <b>{zone['name']}</b> ({zone['city']})<br>
        Zoning: {zone['zoning']}<br>
        Max Height: {zone['max_height']}<br>
        FAR: {zone['far']}<br>
        Hazards: {', '.join(zone['hazards'])}
        """
        folium.CircleMarker(
            location=[zone["lat"], zone["lon"]],
            radius=18,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{zone['name']} ({zone['city']})",
            color=zone["color"],
            fill=True,
            fill_color=zone["color"],
            fill_opacity=0.6,
            weight=2,
        ).add_to(m)

    map_data = st_folium(m, width=700, height=500, returned_objects=["last_object_clicked"])

# ─── Detail Panel ─────────────────────────────────────────────────────────────

with col_detail:
    selected_zone = None
    if map_data and map_data.get("last_object_clicked"):
        click_lat = map_data["last_object_clicked"].get("lat", 0)
        click_lon = map_data["last_object_clicked"].get("lng", 0)

        min_dist = float("inf")
        for zone in CALIFORNIA_ZONES:
            dist = (zone["lat"] - click_lat) ** 2 + (zone["lon"] - click_lon) ** 2
            if dist < min_dist:
                min_dist = dist
                selected_zone = zone

    if selected_zone:
        st.markdown(f'<p class="zone-header">{selected_zone["name"]}</p>', unsafe_allow_html=True)
        st.caption(selected_zone["city"])

        st.markdown(f"**Zoning:** {selected_zone['zoning']}")
        st.markdown(f"**Max Height:** {selected_zone['max_height']}")
        st.markdown(f"**FAR:** {selected_zone['far']}")

        st.divider()

        st.markdown("#### Building Code")
        st.markdown(f"**Base Code:** {selected_zone['code_edition']}")
        st.markdown(f"**Key Amendments:** {selected_zone['key_amendments']}")

        st.divider()

        st.markdown("#### Hazard Exposure")
        hazard_classes = {
            "Seismic": "hazard-seismic",
            "Wildfire": "hazard-wildfire",
            "Flood": "hazard-flood",
            "Coastal": "hazard-flood",
            "Heat": "hazard-heat",
        }
        hazard_html = ""
        for h in selected_zone["hazards"]:
            css_class = "hazard-seismic"
            for key, cls in hazard_classes.items():
                if key.lower() in h.lower():
                    css_class = cls
                    break
            hazard_html += f'<span class="hazard-tag {css_class}">{h}</span> '
        st.markdown(hazard_html, unsafe_allow_html=True)

        st.divider()

        st.markdown("#### Climate Resilience Provisions")
        st.markdown(selected_zone["climate_provisions"])

        st.divider()

        st.markdown("#### Ask about this zone")
        zone_query = st.text_input(
            "Ask a question about this area's building codes...",
            key="zone_query",
            placeholder=f"e.g., What seismic requirements apply in {selected_zone['name']}?",
        )
        if zone_query and OPENAI_KEY:
            with st.spinner("Analyzing..."):
                embeddings_model = OpenAIEmbeddings(model="text-embedding-3-large", api_key=OPENAI_KEY)
                full_query = f"{zone_query} (Context: {selected_zone['city']}, {selected_zone['zoning']})"
                emb = embeddings_model.embed_query(full_query)
                res = httpx.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/match_documents",
                    headers=HEADERS,
                    json={
                        "query_embedding": emb,
                        "match_count": 5,
                        "filter": {"city": selected_zone["city"]},
                    },
                    timeout=30,
                )
                chunks = res.json() if res.status_code == 200 else []
                if not chunks:
                    res = httpx.post(
                        f"{SUPABASE_URL}/rest/v1/rpc/match_documents",
                        headers=HEADERS,
                        json={"query_embedding": emb, "match_count": 5},
                        timeout=30,
                    )
                    chunks = res.json() if res.status_code == 200 else []

                context = "\n".join(c.get("content", "")[:400] for c in chunks[:3])

                llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=OPENAI_KEY)
                response = llm.invoke(
                    f"You are a building code expert for California cities.\n"
                    f"City: {selected_zone['city']}\n"
                    f"Zone: {selected_zone['name']} ({selected_zone['zoning']})\n"
                    f"Code: {selected_zone['code_edition']}\n"
                    f"Hazards: {', '.join(selected_zone['hazards'])}\n\n"
                    f"Retrieved code passages:\n{context}\n\n"
                    f"Question: {zone_query}"
                )
                st.markdown(response.content)

    else:
        st.markdown("### Select a Zone")
        st.markdown("Click on any colored circle on the map to see:")
        st.markdown("- Zoning classification & development limits")
        st.markdown("- Applicable building code & amendments")
        st.markdown("- Hazard exposure (seismic, wildfire, coastal)")
        st.markdown("- Climate resilience provisions")
        st.markdown("- AI-powered code analysis")

        st.divider()

        st.markdown("#### California Cities Overview")
        st.markdown("""
        - **Los Angeles** (3.9M) — 2019 CBC, Seismic Zone D, Wildfire VHFHSZ, Earthquake Hazard Reduction chapters 88-96
        - **San Diego** (1.4M) — 2025 CBC, Coastal + Seismic, Climate Action Plan, Zero-net-energy target
        - **Irvine** (308K) — 2025 CBC, CalGreen Tier 1, EV charging mandates, Swimming pool code
        - **Santa Clarita** (229K) — 2025 CBC, Wildland-urban interface, Defensible space, Energy conservation
        """)

# ─── Bottom: All Cities ──────────────────────────────────────────────────────

st.divider()
st.markdown("### All Cities in Dataset")

comp_cols = st.columns(4)
cities_list = [
    ("Los Angeles, CA", "3.9M", "Seismic, Wildfire", "CBC"),
    ("San Diego, CA", "1.4M", "Seismic, Coastal", "CBC"),
    ("Irvine, CA", "308K", "Seismic", "CBC"),
    ("Santa Clarita, CA", "229K", "Wildfire", "CBC"),
    ("Phoenix, AZ", "1.6M", "Extreme Heat", "IBC"),
    ("Henderson, NV", "325K", "Seismic", "IBC"),
    ("Reno, NV", "264K", "Seismic, Wildfire", "IBC"),
    ("Scottsdale, AZ", "241K", "Extreme Heat", "IBC"),
]

for i, (city, pop, hazard, code) in enumerate(cities_list):
    with comp_cols[i % 4]:
        st.markdown(f"**{city}**")
        st.caption(f"Pop: {pop} | {hazard}")
        st.caption(f"Base: {code}")

st.caption("Powered by GT CURA")
