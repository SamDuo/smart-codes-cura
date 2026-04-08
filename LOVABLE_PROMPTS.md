# GT CURA — Lovable Build Prompts (Midtown Atlanta Focus)

Copy-paste these prompts **in order** into Lovable. Wait for each to finish before sending the next.

---

## SETUP: Before You Start

1. Go to [lovable.dev](https://lovable.dev) → Sign up with GitHub
2. Click "New Project" → name it **GT CURA**
3. After the initial build from Prompt 1, go to **Settings → Integrations → Supabase**
4. Connect with:
   - URL: `https://karnrsbnuqsjtcnaoovp.supabase.co`
   - Anon Key: (get from your Supabase dashboard → Settings → API)
5. Add your Mapbox token as environment variable

---

## PROMPT 1: Initial App — Algoma-Style Dashboard

```
Build a real estate intelligence platform called "GT CURA" — an AI-powered zoning and building code analysis tool focused on Midtown Atlanta. Model the UI after Algoma.co's developer feasibility platform.

LAYOUT (Desktop — full viewport, no scroll on main frame):

1. LEFT SIDEBAR (width: 280px, fixed):
   - Background: #111613 (near-black with green tint)
   - Top: "POLYMETRON" wordmark in Manrope font, weight 700, size 1.1rem, letter-spacing 0.12em, color white. Below it: "Zoning & Code Intelligence" in 0.75rem, color rgba(255,255,255,0.4)
   - Divider line: 1px solid rgba(255,255,255,0.06)
   - Navigation section with vertical links, each with a subtle icon on the left:
     - "Dashboard" (grid icon) — active state: background rgba(44,107,79,0.2), left border 2px solid #2c6b4f, text white
     - "Buildability" (layers icon)
     - "Value Analysis" (trending-up icon)
     - Inactive links: color rgba(255,255,255,0.45), hover: rgba(255,255,255,0.7)
   - Divider
   - "Midtown Atlanta" header in 0.8rem weight 600 white, with a small green pulse dot
   - "SPI-16 District" subtext in 0.7rem rgba(255,255,255,0.4)
   - Divider
   - "Platform Stats" header in 0.65rem uppercase, letter-spacing 0.14em, color rgba(255,255,255,0.3)
   - Three stat cards stacked vertically, each with:
     - Dark card background: rgba(255,255,255,0.03), border 1px solid rgba(255,255,255,0.06), border-radius 8px, padding 12px
     - Large number: "12,550" / "35,290" / "625 ft" in Manrope 1.4rem weight 700 white
     - Label below: "Code Passages Indexed" / "Sales Records (Fulton Co.)" / "Max Height (SPI-16)" in 0.7rem rgba(255,255,255,0.4)
   - Bottom of sidebar: "Georgia Institute of Technology" in 0.7rem rgba(255,255,255,0.35)

2. MAIN AREA (remaining width):
   - Top toolbar (height: 56px):
     - Background: #f6f4f0, border-bottom: 1px solid #e2ddd4
     - Left: breadcrumb "Midtown Atlanta / SPI-16 District" in Manrope 0.85rem, with "SPI-16 District" in weight 600 color #1a1714
     - Right side: persona toggle — two pill buttons side by side:
       - "City Planner" and "Developer" — active one has background #1b3a2d color white, inactive has border 1px solid #e2ddd4 color #7a7267
     - Far right: "Request Demo" button, background #1b3a2d, color white, border-radius 100px, padding 8px 20px

   - Below toolbar: split into two columns
     - LEFT COLUMN (60%): Map area — placeholder div with background #e8e4dc, border-radius 12px, height fills remaining space. Show text "Map Loading..." centered. We will add Mapbox next.
     - RIGHT COLUMN (40%): Detail panel
       - Background: white, border-left: 1px solid #e2ddd4
       - Scrollable content area
       - Default state (no zone selected):
         - Header: "Midtown Atlanta" in Instrument Serif 1.6rem
         - Subtitle: "SPI-16 — One of the Southeast's densest development zones" in 0.88rem color #7a7267
         - Divider
         - "District Overview" section with key-value pairs:
           - Max Height: Up to 625 ft with SAP
           - FAR: 6.0 - 25.0
           - Building Code: 2024 IBC with GA Amendments (eff. Jan 2026)
           - Key Overlays: BeltLine, Midtown DRI, Form-based code
           - Climate: LEED Silver, Cool Roof (SRI >= 64), Tree recompense
           - Transit: MARTA Arts Center & Midtown stations
         - Each pair: label in 0.72rem uppercase #7a7267, value in 0.88rem #1a1714

DESIGN SYSTEM:
- Fonts: Google Fonts — "Instrument Serif" for headings, "Manrope" for body
- Colors: primary #1b3a2d, accent #c0532c, background #f6f4f0, surface white #ffffff, ink #1a1714, muted #7a7267, line #e2ddd4
- Border radius: 8px for cards, 12px for panels, 100px for buttons/pills
- Shadows: 0 1px 3px rgba(26,23,20,0.06), 0 8px 24px rgba(26,23,20,0.04)
- Transitions: all 0.25s ease
- NO generic blue. NO default shadcn blue theme. This is warm, editorial, earth-toned.
```

---

## PROMPT 2: Add Mapbox Map with Midtown Zone Markers

```
Replace the map placeholder with a real Mapbox GL JS map using react-map-gl.

Install: react-map-gl and mapbox-gl

Mapbox token: YOUR_MAPBOX_TOKEN_HERE

Map configuration:
- Center: [33.7845, -84.3834] (Midtown Atlanta)
- Zoom: 13
- Style: mapbox://styles/mapbox/light-v11
- No compass, no zoom controls visible (clean look)
- Border-radius: 12px on the container, overflow hidden

Create a constant MIDTOWN_ZONES with sub-areas within and around Midtown:

const MIDTOWN_ZONES = [
  { id: "spi16-core", name: "SPI-16 Core", lat: 33.7845, lon: -84.3834, subdistrict: "Core", maxHeight: "625 ft (with SAP)", far: "12.0 - 25.0", zoning: "SPI-16 Core Subdistrict", hazards: ["Urban Heat Island"], climate: "LEED Silver minimum, Tree recompense ordinance, Cool Roof SRI >= 64", amendments: "Midtown DRI, Form-based code overlay, Mixed-use requirements, SAP required for all exterior work", color: "#3498db", buildScore: 85 },
  { id: "spi16-village", name: "Midtown Village", lat: 33.7810, lon: -84.3860, subdistrict: "Village", maxHeight: "225 ft", far: "6.0 - 12.0", zoning: "SPI-16 Village Subdistrict", hazards: ["Urban Heat Island"], climate: "LEED Silver, Pedestrian-scale design standards, Active ground floor required", amendments: "Facade transparency minimum 60%, Building stepbacks above 4 stories", color: "#2980b9", buildScore: 78 },
  { id: "spi16-garden", name: "Midtown Garden", lat: 33.7880, lon: -84.3850, subdistrict: "Garden", maxHeight: "150 ft", far: "3.2 - 8.0", zoning: "SPI-16 Garden Subdistrict", hazards: ["Urban Heat Island"], climate: "Enhanced tree canopy requirements, Residential-scale transitions", amendments: "Residential compatibility standards, Reduced parking minimums near MARTA", color: "#1abc9c", buildScore: 72 },
  { id: "spi16-transition", name: "Transition Zone", lat: 33.7790, lon: -84.3810, subdistrict: "Transition", maxHeight: "75 ft", far: "1.5 - 3.2", zoning: "SPI-16 Transition Subdistrict", hazards: ["Urban Heat Island"], climate: "Neighborhood compatibility, Infill design standards", amendments: "Adaptive reuse incentives, Accessory dwelling unit provisions", color: "#27ae60", buildScore: 58 },
  { id: "gt-campus", name: "Georgia Tech / Civic", lat: 33.7756, lon: -84.3963, subdistrict: "Civic/Institutional", maxHeight: "100 ft (campus standards)", far: "2.0 - 4.0", zoning: "SPI-16 Civic/Institutional", hazards: ["Urban Heat Island", "Stormwater"], climate: "Campus sustainability plan, Green building standards, Stormwater management", amendments: "Institutional overlay, Campus master plan compliance required", color: "#8e44ad", buildScore: 62 },
  { id: "beltline-east", name: "BeltLine Eastside Trail", lat: 33.7845, lon: -84.3720, subdistrict: "BeltLine Overlay", maxHeight: "150 ft (with overlay bonuses)", far: "3.2 + 20% density bonus", zoning: "MRC-3 + BeltLine Overlay", hazards: ["Urban Heat Island", "Flood (Clear Creek)"], climate: "BeltLine green space connectivity, Green building incentives, Flood mitigation", amendments: "15% inclusionary housing required, Active ground floor, No surface parking facing trail", color: "#e67e22", buildScore: 68 },
];

Render each zone as a pulsing circle marker on the map with its color. Show zone name on hover tooltip.

When a zone marker is clicked:
1. Map flies to that zone (flyTo with zoom 15, duration 1.2s)
2. Update React state with the selected zone
3. Right detail panel updates with zone info

Add a subtle "POLYMETRON" watermark in top-left of map, 0.7rem rgba(0,0,0,0.12).
```

---

## PROMPT 3: Zone Detail Panel — Tabbed Interface

```
When a zone is selected (from clicking a map marker), update the right panel to show zone details in a tabbed layout. Model this after Algoma.co's sequential analysis panels.

ZONE SELECTED STATE — Right Panel:

1. ZONE HEADER (sticky at top of panel):
   - Zone name in Instrument Serif 1.5rem, color #1a1714
   - Below it: subdistrict + zoning in 0.82rem color #7a7267 (e.g., "Core Subdistrict — SPI-16")
   - Below that: colored hazard chips:
     - "Urban Heat Island": bg #fff3e0, color #e65100
     - "Flood*": bg #e3f2fd, color #1565c0
     - "Stormwater": bg #e8f5e9, color #2e7d32
   - Divider

2. TAB BAR — four tabs:
   "Overview" | "Code & Climate" | "Feasibility" | "Ask AI"
   - Active: border-bottom 2px solid #1b3a2d, color #1a1714, weight 600
   - Inactive: color #7a7267

3. TAB "Overview":
   - 2-column grid of stat cards:
     - "Max Height" → large value
     - "FAR" → from zone data
     - "Setbacks" → "0-10 ft"
     - "Parking" → "Reduced (near MARTA)"
   - Each card: bg #faf8f4, border 1px solid #e2ddd4, border-radius 8px, padding 14px
   - Label: 0.68rem uppercase muted, Value: 1.1rem weight 700
   - Below cards: "Key Amendments" section with zone.amendments text

4. TAB "Code & Climate":
   - "Climate Resilience Provisions" — bulleted list from zone.climate, green dots
   - "Building Code" section:
     - "Base: 2024 IBC with Georgia Amendments"
     - "Effective: January 1, 2026"
     - Key provisions list:
       - "Cool Roof: SRI >= 64, reflectance >= 0.55"
       - "Stormwater: First 1-inch green infrastructure retention"
       - "Energy: IECC 2015 + LEED Silver (SPI-16)"
       - "Trees: 75,000 new by 2030, recompense for removals"
       - "Benchmarking: Buildings >25K sq ft report annually"

5. TAB "Feasibility" — inline buildability summary:
   - Two side-by-side mini cards:
     LEFT "Permitted":
       - Max Height, FAR, Ground Floor requirement
       - Green top border (3px #2c6b4f)
     RIGHT "Practical":
       - Construction cost range (based on zone type: SPI-16 Core = "$350-450/sq ft", Village = "$300-400/sq ft", Garden = "$250-350/sq ft", Transition = "$180-250/sq ft", BeltLine = "$250-350/sq ft")
       - Absorption: "18-24 mo" for high-rise zones, "12-16 mo" for mid-rise
       - Regulatory complexity: "High" (red) for Core, "Moderate" (amber) for others, "Low" (green) for Transition
       - Amber top border (3px #b8953a)
   - Buildability Score circle below:
     - SVG donut chart, score from zone.buildScore
     - Green >= 70, amber 50-69, red < 50
     - Large number centered, label "Buildability Score"

6. TAB "Ask AI" — we'll build this next.

Smooth fade transition between tabs. "Back to district" ghost button to deselect zone.
```

---

## PROMPT 4: AI Chat with Pre-Cached Midtown Responses

```
Build the "Ask AI" tab. Chat interface for asking questions about Midtown Atlanta zoning and building codes.

LAYOUT:

1. PRESET BUTTONS (top, 2x2 grid):
   - "Fire code for high-rise"
   - "Cool roof cost impact"
   - "SPI-16 zoning limits"
   - "BeltLine overlay rules"
   Style: bg #faf8f4, border 1px solid #e2ddd4, border-radius 100px, padding 6px 14px, font 0.75rem, hover: bg #1b3a2d color white

2. CHAT MESSAGES (scrollable):
   - User: align right, bg #1b3a2d, color white, border-radius 14px 14px 4px 14px
   - AI: align left, bg #faf8f4, border 1px solid #e2ddd4, border-radius 14px 14px 14px 4px, renders markdown
   - Source citation below AI: 0.7rem italic #7a7267

3. INPUT (sticky bottom):
   - Full-width input, border-radius 100px, placeholder "Ask about Midtown zoning, codes, permits..."
   - Send button: 36px circle, bg #1b3a2d

4. PRE-CACHED RESPONSES — match by keywords, show typing dots for 1.5s then reveal:

RESPONSE 1 — keywords: ["fire", "high-rise", "sprinkler", "nfpa"]
Question: "What fire protection is required for a 20-story building in Midtown?"
Answer: "**High-Rise Fire Protection — SPI-16 (20-story / ~240 ft):**\n\nUnder the 2024 IBC with Georgia Amendments:\n\n**1. Automatic Sprinkler System (IBC Section 903)**\n- NFPA 13 system required throughout\n- High-rise provisions triggered at 75 ft (IBC Section 403)\n- Secondary water supply required\n\n**2. Fire Alarm & Detection (IBC Section 907)**\n- Addressable fire alarm with voice evacuation\n- Smoke detectors in all common areas and elevator lobbies\n\n**3. Standpipe System (IBC Section 905)**\n- Class I standpipe in all stairwells\n- Fire department connection at grade\n\n**4. Structural Fire Resistance**\n- Type I-A or I-B construction\n- Floor assemblies: 2-hour rating\n- Structural frame: 3-hour rating\n\n**5. Emergency Systems**\n- Fire service access elevator (buildings >120 ft)\n- Stairwell pressurization\n- Fire command center on ground floor\n\n**Cost estimate:** ~$15-25/sq ft for fire protection systems."
Sources: "IBC Section 403, IBC Section 903, GA DCA 2024 Amendments, NFPA 13"

RESPONSE 2 — keywords: ["cool roof", "roof", "sri", "reflectance"]
Question: "What are the cool roof requirements and cost impact?"
Answer: "**Atlanta Cool Roof Ordinance (25-O-1310):**\n\n**Requirements (Effective 2025):**\n- Low-slope roofs: SRI >= 64, solar reflectance >= 0.55\n- Steep-slope roofs: SRI >= 25, reflectance >= 0.20\n- Applies to new construction AND major reroofing (>50% of roof)\n- Green/vegetated roofs covering >= 50% qualify as compliant\n- Roofs with >= 75% solar panels are exempt\n\n**Cost Impact (20-story, ~15,000 sq ft roof):**\n\n| Item | Standard | Cool Roof | Delta |\n|------|----------|-----------|-------|\n| Materials | $12-18/sqft | $14-22/sqft | +$2-4/sqft |\n| Total | $180-270K | $210-330K | +$30-60K |\n| Annual HVAC savings | — | 10-15% reduction | -$8-15K/yr |\n| **Payback** | — | — | **3-5 years** |\n\nAtlanta is the only city in our dataset with a mandatory cool roof ordinance."
Sources: "Cool Roof Ordinance 25-O-1310, LEED v4.1 Heat Island Credit"

RESPONSE 3 — keywords: ["zoning", "height", "far", "limit", "spi-16", "spi16"]
Question: "What are the SPI-16 zoning limits for development?"
Answer: "**SPI-16 Midtown — Development Envelope:**\n\n| Subdistrict | Max Height | FAR | Key Requirement |\n|------------|-----------|-----|----------------|\n| **Core** | 625 ft (with SAP) | 12.0-25.0 | SAP for all exterior work |\n| **Village** | 225 ft | 6.0-12.0 | 60% facade transparency |\n| **Garden** | 150 ft | 3.2-8.0 | Residential-scale transitions |\n| **Transition** | 75 ft | 1.5-3.2 | Neighborhood compatibility |\n| **Civic** | 100 ft | 2.0-4.0 | Campus master plan compliance |\n\n**Key Requirements:**\n- **SAP (Special Administrative Permit)** required for all exterior work\n- Active ground-floor uses mandatory\n- Structured parking required above 100 spaces\n- No surface parking between building and street\n- Pedestrian-level design standards enforced\n\n**Density Bonuses:** Up to 20% FAR increase for affordable housing units or public amenities.\n\n**Transit:** MARTA Arts Center and Midtown stations reduce parking requirements."
Sources: "SPI-16 Zoning Code, City of Atlanta Dept of City Planning"

RESPONSE 4 — keywords: ["beltline", "overlay", "inclusionary", "affordable"]
Question: "How does the BeltLine Overlay affect development?"
Answer: "**BeltLine Overlay District — Midtown Eastside:**\n\n**Density Bonuses:**\n- FAR increases up to 20% for developments providing affordable housing or public amenities\n- Trail connectivity counts toward bonus\n\n**Design Requirements:**\n- Active ground-floor uses within 50 ft of trail\n- No surface parking between building and trail\n- 60% minimum facade transparency at ground level\n- Building stepbacks above 4 stories\n- Pedestrian-scale lighting required\n\n**Anti-Displacement (Inclusionary Zoning):**\n- Developments >10 units: **15% affordable units** (at/below 80% AMI)\n- OR pay in-lieu fees to BeltLine Affordable Housing Trust Fund\n- 20-year affordability covenant recorded on property\n- Affordable units must match market-rate in size and finish\n\n**Connectivity:**\n- Direct pedestrian access to BeltLine trail required\n- Bicycle parking minimums increased 50% over base zoning\n\n**Key Takeaway:** BeltLine Overlay simultaneously increases development potential while requiring housing affordability and design quality."
Sources: "BeltLine Zoning Overlay, BeltLine Affordable Housing Trust Fund"

RESPONSE 5 — keywords: ["climate", "resilience", "stormwater", "energy"]
Question: "What climate resilience provisions apply in Midtown?"
Answer: "**Atlanta Climate-Aligned Building Provisions (5 active):**\n\n1. **Cool Roof Ordinance (2025)** — SRI >= 64, reflectance >= 0.55. Targets heat island.\n2. **Energy Benchmarking (2015)** — Annual reporting for buildings >25K sq ft.\n3. **LEED Silver (SPI-16)** — Mandatory for large Midtown projects.\n4. **Stormwater (2013)** — First 1-inch retention via green infrastructure. Nation-leading.\n5. **Tree Protection** — 75,000 new trees by 2030. Recompense ordinance for removals.\n\n**Climate Resilience Plan (April 2025):**\n- 59% GHG reduction by 2030\n- 100% clean energy citywide by 2050\n- Focus: extreme heat, drought, flooding\n\n**Gap:** No mandatory electrification for new buildings yet (LA and San Diego are leading here).\n\nAtlanta has more active climate-aligned building provisions than any comparable Sun Belt city."
Sources: "Atlanta Climate Resilience Plan 2025, Cool Roof Ordinance 25-O-1310, GA DCA 2024 IBC Amendments"

RESPONSE 6 — keywords: ["value", "opportunity", "delta", "gap", "invest"]
Question: "Where are the development opportunities in Midtown?"
Answer: "**Midtown Value Analysis (Fulton County Sales Data, 2011-2022):**\n\n**25,757 sales** in the Midtown area. Key signals:\n\n| Period | Sale/FMV Ratio | Signal |\n|--------|---------------|--------|\n| 2012 | 0.79 | Post-recession — properties 21% below assessed value |\n| 2017 | 1.35 | Peak — properties sold 35% ABOVE assessed value |\n| 2022 | 1.03 | Stabilized — fair market pricing |\n\n**Swing:** 71% ratio swing from trough (0.79) to peak (1.35) in 5 years.\n\n**Opportunity Zones in Midtown:**\n- **Transition subdistrict:** Lowest density today, permitted FAR 1.5-3.2. Adaptive reuse + ADU provisions make infill attractive.\n- **BeltLine Eastside:** Overlay bonuses (+20% FAR) offset inclusionary requirements. Trail adjacency commands 15-20% rent premium.\n\n**Vacant land:** 1,777 parcels in broader Midtown area — each represents buildability gap.\n\n**Key Takeaway:** Midtown is near equilibrium (ratio 1.03). Biggest upside now is in Transition zones and BeltLine overlay areas where density bonuses remain unlocked."
Sources: "Fulton County Sales Records (HUP Lab), atlanta-tracts.geojson HVI analysis"

DEFAULT response (no keyword match):
"I can analyze zoning requirements, building codes, fire protection, climate provisions, and development feasibility for any subdistrict in Midtown Atlanta. Try asking about fire codes, cool roof costs, SPI-16 zoning limits, or BeltLine overlay rules."
```

---

## PROMPT 5: Value Delta Analysis View

```
Create the "Value Analysis" page accessible from sidebar navigation. This shows Midtown Atlanta property market data from Fulton County sales records.

LAYOUT:

1. PAGE HEADER:
   - "Value Delta Analysis" in Instrument Serif 1.8rem
   - "Sale price vs. assessed value — Midtown Atlanta, 2011-2022" in 0.88rem #7a7267

2. STAT CARDS ROW (4 cards, horizontal):
   - "25,757" — "Midtown Sales" 
   - "1.02" — "Median Sale/FMV Ratio"
   - "3,741" — "High Opportunity Sales" (ratio > 1.3)
   - "1,777" — "Vacant Parcels"
   Card style: bg white, border 1px solid #e2ddd4, border-radius 8px, padding 16px
   Number: Manrope 1.6rem weight 700, Label: 0.72rem #7a7267

3. MAIN CONTENT — two columns (55% / 45%):

   LEFT: Year-over-year line chart showing Sale/FMV ratio from 2011-2022.
   Use recharts library (install it).
   Data: [
     {year: "2011", ratio: 1.00}, {year: "2012", ratio: 0.79}, {year: "2013", ratio: 1.00},
     {year: "2014", ratio: 1.10}, {year: "2015", ratio: 1.07}, {year: "2016", ratio: 1.00},
     {year: "2017", ratio: 1.35}, {year: "2018", ratio: 1.07}, {year: "2019", ratio: 1.02},
     {year: "2020", ratio: 1.03}, {year: "2021", ratio: 1.02}, {year: "2022", ratio: 1.03}
   ]
   - Line color: #1b3a2d
   - Reference line at y=1.0 (dashed, #e2ddd4) labeled "Fair Value"
   - Highlight 2012 dip (red dot, annotation "Post-recession trough")
   - Highlight 2017 peak (green dot, annotation "Peak — 35% above FMV")
   - Chart background: white with subtle grid
   - Chart title: "Sale/FMV Ratio — Midtown Atlanta"

   RIGHT: Value delta tier breakdown as horizontal bar chart:
   Data:
   - "Fair Value (0.9-1.1)": 8,847 — color #2c6b4f
   - "Hot Market (1.1-1.3)": 3,091 — color #b8953a
   - "Surging (>1.3)": 3,525 — color #c0532c
   - "Below Market (0.7-0.9)": 939 — color #e67e22
   - "Distressed (<0.7)": 2,017 — color #e74c3c
   Chart title: "Value Delta Distribution"

4. INSIGHT CARDS (below charts, 3 columns):
   Three cards with left accent border (3px):

   Card 1 (border #c0532c):
   "**71% Swing**" header
   "Midtown ratio swung from 0.79 (2012) to 1.35 (2017) — fastest appreciation in the dataset. Market consistently outpaced tax assessments."

   Card 2 (border #2c6b4f):  
   "**1,777 Vacant Parcels**" header
   "Vacant land in high-density SPI-16 zones represents the largest buildability gap. FAR permits up to 25.0 — most parcels are dramatically underutilized."

   Card 3 (border #b8953a):
   "**BeltLine Premium**" header
   "Old Fourth Ward (adjacent BeltLine) hit 1.51 ratio in 2017 — trail adjacency commands 15-20% rent premium. Overlay density bonuses remain under-leveraged."

5. DATA SOURCE footer:
   - "Source: Fulton County Tax Assessor via Georgia Tech HUP Lab | 427,617 total county records | 2011-2022"
   - Font: 0.72rem #7a7267
```

---

## PROMPT 6: Buildability Analysis View

```
Create the "Buildability" page from sidebar navigation. Shows permitted envelope vs practical feasibility for Midtown subdistricts.

LAYOUT:

1. HEADER:
   - "Buildability Analysis" in Instrument Serif 1.8rem
   - "Permitted development envelope vs. practical feasibility" in 0.88rem #7a7267

2. SUBDISTRICT SELECTOR:
   - Horizontal row of pill buttons for each Midtown subdistrict:
     "SPI-16 Core" | "Village" | "Garden" | "Transition" | "Georgia Tech" | "BeltLine"
   - Active: bg matches zone color, text white
   - Default: "SPI-16 Core" selected

3. SIDE-BY-SIDE CARDS (changes with selection):

   LEFT — "Permitted Envelope" (green top border 4px #2c6b4f):
   Stats grid:
   - Max Height: from zone data (large bold)
   - FAR: from zone data
   - Zoning: zone classification
   - Parking: "Reduced near MARTA"
   - Ground Floor: "Active uses required"
   - SAP: "Required" or "Not required"
   Label: 0.68rem uppercase muted, Value: 1rem weight 600

   RIGHT — "Feasibility" (amber top border 4px #b8953a):
   - Construction Cost:
     - Core: "$350-450/sq ft"
     - Village: "$300-400/sq ft"
     - Garden/BeltLine: "$250-350/sq ft"
     - Transition: "$180-250/sq ft"
     - GT: "$200-300/sq ft"
   - Absorption: "18-24 mo" (Core/Village), "12-16 mo" (Garden/BeltLine), "8-12 mo" (Transition)
   - Regulatory Complexity: "High" (red chip) for Core, "Moderate" (amber) for Village/Garden/BeltLine, "Low" (green) for Transition
   - Timeline to Permits: "8-12 weeks + SAP" for SPI zones, "4-6 weeks" for Transition

4. BUILDABILITY SCORE (centered below cards):
   - Large SVG donut/radial gauge
   - Score from zone.buildScore: Core=85, Village=78, Garden=72, Transition=58, GT=62, BeltLine=68
   - Color: >= 70 green, 50-69 amber, < 50 red
   - Center: large number + "/ 100"
   - Label: "Buildability Score"

5. KEY INSIGHTS (below gauge):
   Card with left border 3px solid #c0532c, bg #faf8f4:
   Dynamic bullet points based on selected subdistrict:
   - Core: "SAP adds 8-12 weeks. LEED Silver adds 3-5% cost but unlocks TAD incentives. Cool Roof: $2-4/sq ft premium, 3-5 year payback."
   - Village: "Facade transparency 60% minimum increases glass costs. Stepback requirements above 4 stories reduce leasable area by ~5%."
   - Garden: "Residential-scale transitions limit height near existing neighborhoods. Enhanced tree canopy may restrict site coverage."
   - Transition: "Lowest barriers to entry. Adaptive reuse incentives reduce soft costs. ADU provisions create infill opportunity."
   - GT: "Campus master plan compliance required. Institutional overlay limits commercial uses."
   - BeltLine: "15% inclusionary housing required — bake into pro forma from day one. 20% FAR bonus offsets affordable unit costs. Trail adjacency = 15-20% rent premium."
```

---

## PROMPT 7: Polish & Finishing Touches

```
Apply finishing touches across the entire app:

1. LOADING & TRANSITIONS:
   - Skeleton loaders (pulsing gray) when switching views
   - Fade-in (opacity 0→1, 0.3s) on all page transitions
   - Slide-in from left (translateX -8px → 0, 0.2s) for panel content

2. STAT ANIMATIONS:
   - Numbers in sidebar and stat cards count up from 0 on first appear (1.2s ease-out)

3. MAP POLISH:
   - Zone markers pulse subtly (ring animation, opacity 0.3→0, scale 1→2, repeat)
   - Hover: marker grows (scale 1.15)
   - Selected zone: full opacity, others dim to 0.35
   - Selected zone gets a glowing ring effect

4. RESPONSIVE:
   - < 1024px: sidebar collapses to hamburger icon
   - < 768px: map stacks above detail panel
   - Map minimum 50vh on mobile
   - Stat cards wrap to 2 columns on tablet, 1 on mobile

5. PERSONA TOGGLE:
   - Persists across all views
   - When "City Planner" is active: preset queries show climate/equity questions
   - When "Developer" is active: preset queries show feasibility/cost questions
   - Default to "Developer" on load

6. REQUEST DEMO:
   - Click shows toast: "Contact cura@gatech.edu for demo access"
   - Toast: bottom-right, auto-dismiss after 4s, bg #1b3a2d, white text

7. META:
   - Title: "GT CURA | Midtown Atlanta Zoning Intelligence"
   - Description: "AI-powered zoning and building code analysis for Midtown Atlanta SPI-16. Analyze development feasibility, climate provisions, and value opportunities."
   - Favicon: dark green circle (#1b3a2d) with white "P"

8. EMPTY STATES:
   - If navigating to Buildability without selecting a zone, show the subdistrict selector prominently
   - If Ask AI has no messages yet, show a welcome: "Ask me anything about Midtown Atlanta's building codes, zoning requirements, or development feasibility."
```

---

## AFTER ALL PROMPTS

### Quick Enhancements:
1. Upload `atlanta-tracts.geojson` to public/ → add tract polygons colored by HVI to Dashboard map
2. Connect Supabase if you want live RAG queries later

### Get Shareable URL:
- Lovable auto-deploys → share `your-project.lovable.app` with investors

### Demo Script (3 minutes):
1. **Open Dashboard** → Midtown map with 6 subdistrict markers
2. **Click SPI-16 Core** → panel fills: 625 ft height, FAR 25.0, hazard chips
3. **Code & Climate tab** → 5 climate provisions, cool roof details
4. **Feasibility tab** → permitted vs practical side-by-side, score gauge 85
5. **Ask AI tab** → click "Fire code for high-rise" → watch cited response appear
6. **Value Analysis** → line chart showing 2012 trough to 2017 peak, "71% swing"
7. **Buildability** → flip between Core (85) and BeltLine (68), show inclusionary housing insight
8. **Close:** "12,550 indexed code passages. 35,290 sales records. One platform."
