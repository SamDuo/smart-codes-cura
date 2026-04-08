# GT CURA Demo: Zoning & Building Code Intelligence for Midtown Atlanta

## What We're Building

An interactive, map-based intelligence platform that lets developers, city planners, and investors instantly understand zoning laws, building code requirements, and climate resilience provisions for any location in Midtown Atlanta.

**Demo target:** Investor presentation showing GT CURA's Policy Intelligence module in action.

## Why Midtown Atlanta

- **SPI-16 District** -- one of Atlanta's most active development zones with form-based code overlay
- **Max height up to 625 ft** with Special Administrative Permit
- **FAR 6.0-25.0** -- among the densest allowed in the Southeast
- **BeltLine adjacency** -- subject to BeltLine Overlay District requirements
- **Climate relevance** -- urban heat island, stormwater management, cool roof ordinance all apply
- **GT relationship** -- GT CURA's home base; GT CURA's home base

## Data Ingested

| Source | Chunks | Description |
|--------|--------|-------------|
| GA DCA 2024 IBC Amendments | 11 | State-level building code amendments (effective Jan 1, 2026) |
| Combined 2026 GA Amendments | 576 | All Georgia amendments to 2024 ICC codes (IBC, IRC, IMC, IFGC, IPC) |
| Atlanta Climate Resilience | 4 | Cool Roof Ordinance, stormwater, energy benchmarking, tree protection |
| 8-City Amendment Database | 10,428 | Cross-jurisdiction comparison (LA, Phoenix, San Diego, Henderson, Irvine, Reno, Santa Clarita, Scottsdale) |
| LA Building Code Chapters | 1,531 | Fire safety, structural design, accessibility (2019 CBC) |
| **Total** | **~12,550** | **Indexed passages across 9 cities** |

## Demo Flow (Investor Presentation)

### Scene 1: "The Problem" (30 seconds)
> A developer wants to build a 20-story mixed-use tower in Midtown Atlanta. Today, they'd hire a code consultant ($15-25K), wait weeks for a zoning analysis, and still not know how Atlanta's codes compare to other Sun Belt cities.

### Scene 2: "GT CURA in Action" (2 minutes)

1. **Open the Map Intelligence page** → Atlanta map with 8 zoning districts
2. **Click Midtown / SPI-16** → instantly see:
   - Zoning: SPI-16 (Midtown Special Public Interest)
   - Max height: up to 625 ft with SAP
   - FAR: 6.0-25.0
   - Hazards: Urban Heat Island
   - Climate provisions: LEED Silver minimum, cool roof, tree recompense
   - Key amendments: Midtown DRI, form-based code overlay, mixed-use requirements

3. **Ask a question in the chat**: "What fire protection systems are required for a 20-story building in Midtown Atlanta?"
   → AI retrieves from GA 2024 IBC amendments + LA comparison data
   → Cites specific sections (NFPA 13, Section 903, high-rise provisions)

4. **Cross-jurisdiction comparison**: "How does Atlanta's building code compare to Phoenix's for mixed-use development?"
   → Shows differences in base code (IBC with GA amendments vs IBC with AZ amendments)
   → Highlights Atlanta's climate provisions (cool roof, stormwater) that Phoenix lacks

### Scene 3: "The Moat" (30 seconds)
> Show the stats sidebar: 9 cities, 12,550 indexed passages, 11,163 code sections tracked, 2,550 amendment events.
> "No competitor has this cross-jurisdiction amendment intelligence. First Street does climate risk. Algoma does zoning. We do both, plus the policy layer that connects them."

## Technical Architecture

```
User clicks map location
        ↓
[Folium Map] → Zone identification (SPI-16, R-5, MRC-3, etc.)
        ↓
[Zoning Data] → Height, FAR, overlay districts, hazard exposure
        ↓
User asks question
        ↓
[OpenAI Embeddings] → text-embedding-3-large (3072 dim)
        ↓
[Supabase Vector Search] → Top 8 passages from 12,550 chunks
        ↓
[Neo4j Graph Context] → Adoption timelines, cross-jurisdiction links
        ↓
[GPT-4o] → Structured answer with citations
        ↓
[Streamlit UI] → Map + detail panel + chat
```

## Key Queries to Demo

1. "What are the fire code requirements for a high-rise building in Midtown Atlanta?"
2. "Does Atlanta require cool roofs? What are the specifications?"
3. "How does Atlanta's stormwater management compare to other cities?"
4. "What seismic design category applies in Atlanta vs Los Angeles?"
5. "Which cities have the most recent building code adoptions?"
6. "What energy benchmarking requirements apply to commercial buildings in Atlanta?"

## Midtown SPI-16 Zoning Details

- **District:** SPI-16 (Midtown Special Public Interest District)
- **Subdistricts:** Core, Midtown Garden, Midtown Village, Transition, Civic/Institutional
- **Height:** Varies by subdistrict; Core allows 625 ft with SAP
- **FAR:** 6.0-25.0 depending on subdistrict and bonuses
- **Setbacks:** Minimal (0-10 ft); pedestrian-level design standards
- **Parking:** Reduced minimums; structured parking required above 100 spaces
- **Design Standards:** Active ground floor uses, building stepbacks, facade transparency
- **Transit:** MARTA Arts Center and Midtown stations
- **BeltLine:** Eastern edge touches BeltLine Overlay District
- **Key requirement:** Special Administrative Permit (SAP) for all exterior work

## Atlanta Climate Resilience Provisions (Demo Highlights)

| Provision | Year | Requirement | Demo Value |
|-----------|------|-------------|------------|
| Cool Roof Ordinance | 2025 | SRI ≥ 64, reflectance ≥ 0.55 | Heat island mitigation |
| Stormwater Management | 2013 | Green infrastructure for first 1" rainfall | Nation-leading |
| Energy Benchmarking | 2015 | Annual reporting for buildings >25K sq ft | Data-driven |
| Tree Protection | Updated | 75,000 new trees by 2030 | Canopy target |
| Clean Energy | 2017 | 100% clean energy citywide by 2050 | Ambition signal |
| Climate Resilience Plan | 2025 | 59% GHG reduction by 2030 | Just launched |

## Files

- `pages/4_🗺️_Map_Intelligence.py` -- Map-based demo with 8 Atlanta zones
- `pages/3_🏙️_Policy_Intelligence.py` -- Cross-jurisdiction chatbot
- `Introduction.py` -- GT CURA landing page
- `ingest_atlanta.py` -- Atlanta data ingestion script
- `ingest_amendments.py` -- Multi-city amendment pipeline
- `eval_methodology.py` -- Evaluation framework (56 benchmark queries)

## Next Steps

1. Add real GIS zoning overlay from Atlanta Open Data Hub (ArcGIS)
2. Integrate building permit data (2019-2024) for development activity
3. Add Fulton County parcel data for property-level analysis
4. Connect to Georgia DFIRM flood maps for risk overlay
5. Deploy to Streamlit Cloud or GT PACE for shareable demo URL
