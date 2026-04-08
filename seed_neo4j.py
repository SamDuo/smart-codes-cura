"""
Seed Neo4j Aura with building code amendment knowledge graph.

Schema:
  (City)-[:ADOPTED]->(AmendmentDoc)-[:CONTAINS]->(CodeSection)
  (AmendmentDoc)-[:BASED_ON]->(ModelCode)
  (City)-[:IN_STATE]->(State)

This creates a graph that enables:
  - Cross-jurisdiction queries: "Compare LA vs Henderson amendments"
  - Temporal queries: "What changed between 2019 and 2022 in San Diego?"
  - Multi-hop: "Which cities adopted amendments to Section 903?"
"""

import json
import os
import re
from neo4j import GraphDatabase

# ─── Config ───────────────────────────────────────────────────────────────────

NEO4J_URI = os.environ.get("NEO4J_URI", "")
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

AMENDMENT_DIR = "c:/Users/qduong7/Downloads/04_Amendment"

# City metadata from Amendments.xlsx
CITIES = {
    "Henderson": {"state": "NV", "population": 324523, "model_code": "IBC"},
    "Irvine": {"state": "CA", "population": 307670, "model_code": "CBC"},
    "Los Angeles": {"state": "CA", "population": 3857897, "model_code": "CBC"},
    "Phoenix": {"state": "AZ", "population": 1608139, "model_code": "IBC"},
    "Reno": {"state": "NV", "population": 264165, "model_code": "IBC"},
    "San Diego": {"state": "CA", "population": 1385061, "model_code": "CBC"},
    "Santa Clarita": {"state": "CA", "population": 229021, "model_code": "CBC"},
    "Scottsdale": {"state": "AZ", "population": 241361, "model_code": "IBC"},
}

# Amendment adoption data from Amendments.xlsx
ADOPTIONS = {
    "Henderson": [
        {"year": 2013, "type": "BC", "edition": "2013_IBC"},
        {"year": 2013, "type": "RC", "edition": "2013_IRC"},
        {"year": 2018, "type": "RC", "edition": "2018_IRC"},
        {"year": 2018, "type": "BC", "edition": "2016_IBC"},
        {"year": 2020, "type": "BC", "edition": "2018_IBC"},
        {"year": 2021, "type": "BC", "edition": "2021_IBC"},
        {"year": 2021, "type": "RC", "edition": "2021_IRC"},
        {"year": 2024, "type": "BC", "edition": "2024_IBC"},
        {"year": 2024, "type": "RC", "edition": "2024_IRC"},
    ],
    "Irvine": [
        {"year": 2010, "type": "Whole", "edition": "2010_CBC"},
        {"year": 2013, "type": "Whole", "edition": "2013_CBC"},
        {"year": 2019, "type": "Whole", "edition": "2019_CBC"},
        {"year": 2022, "type": "Whole", "edition": "2022_CBC"},
        {"year": 2025, "type": "Whole", "edition": "2025_CBC"},
    ],
    "Los Angeles": [
        {"year": 2011, "type": "BC", "edition": "2010_CBC"},
        {"year": 2011, "type": "RC", "edition": "2010_CRC"},
        {"year": 2014, "type": "BC", "edition": "2013_CBC"},
        {"year": 2014, "type": "RC", "edition": "2013_CRC"},
        {"year": 2017, "type": "Whole", "edition": "2016_CBC"},
        {"year": 2020, "type": "Whole", "edition": "2019_CBC"},
        {"year": 2023, "type": "Whole", "edition": "2022_CBC"},
        {"year": 2026, "type": "Whole", "edition": "2025_CBC"},
    ],
    "Phoenix": [
        {"year": 2018, "type": "BC", "edition": "2018_IBC"},
        {"year": 2018, "type": "RC", "edition": "2018_IRC"},
        {"year": 2024, "type": "BC", "edition": "2024_IBC"},
        {"year": 2024, "type": "RC", "edition": "2024_IRC"},
    ],
    "Reno": [
        {"year": 2012, "type": "Whole", "edition": "2012_IBC"},
        {"year": 2018, "type": "Whole", "edition": "2018_IBC"},
        {"year": 2024, "type": "Whole", "edition": "2024_IBC"},
    ],
    "San Diego": [
        {"year": 2016, "type": "Whole", "edition": "2016_CBC"},
        {"year": 2019, "type": "Whole", "edition": "2019_CBC"},
        {"year": 2022, "type": "Whole", "edition": "2022_CBC"},
        {"year": 2025, "type": "Whole", "edition": "2025_CBC"},
    ],
    "Santa Clarita": [
        {"year": 2013, "type": "Whole", "edition": "2013_CBC"},
        {"year": 2016, "type": "Whole", "edition": "2016_CBC"},
        {"year": 2019, "type": "Whole", "edition": "2019_CBC"},
        {"year": 2022, "type": "Whole", "edition": "2022_CBC"},
        {"year": 2025, "type": "Whole", "edition": "2025_CBC"},
    ],
    "Scottsdale": [
        {"year": 2021, "type": "BC", "edition": "2021_IBC"},
    ],
}


def create_schema(session):
    """Create constraints and indexes."""
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:City) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:State) REQUIRE s.code IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (mc:ModelCode) REQUIRE mc.edition IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (ad:AmendmentDoc) REQUIRE ad.doc_id IS UNIQUE",
    ]
    for cypher in constraints:
        session.run(cypher)
    print("Schema constraints created.")


def seed_states(session):
    """Create State nodes."""
    states = {"CA": "California", "NV": "Nevada", "AZ": "Arizona"}
    for code, name in states.items():
        session.run(
            "MERGE (s:State {code: $code}) SET s.name = $name",
            code=code, name=name,
        )
    print(f"Created {len(states)} State nodes.")


def seed_model_codes(session):
    """Create ModelCode nodes for all referenced editions."""
    editions = set()
    for city_adoptions in ADOPTIONS.values():
        for a in city_adoptions:
            editions.add(a["edition"])

    for edition in editions:
        parts = edition.split("_")
        year = int(parts[0])
        code_family = parts[1]  # IBC, CBC, IRC, CRC
        session.run(
            "MERGE (mc:ModelCode {edition: $edition}) "
            "SET mc.year = $year, mc.code_family = $code_family",
            edition=edition, year=year, code_family=code_family,
        )
    print(f"Created {len(editions)} ModelCode nodes.")


def seed_cities(session):
    """Create City nodes with metadata."""
    for city_key, meta in CITIES.items():
        display_name = meta.get("display_name", city_key)
        session.run(
            "MERGE (c:City {name: $name}) "
            "SET c.display_name = $display_name, c.population = $population, "
            "    c.model_code_family = $model_code "
            "WITH c "
            "MATCH (s:State {code: $state}) "
            "MERGE (c)-[:IN_STATE]->(s)",
            name=city_key, display_name=display_name,
            population=meta["population"], model_code=meta["model_code"],
            state=meta["state"],
        )
    print(f"Created {len(CITIES)} City nodes with state relationships.")


def seed_amendment_docs(session):
    """Create AmendmentDoc nodes and relationships."""
    total = 0
    for city_key, adoptions in ADOPTIONS.items():
        for a in adoptions:
            doc_id = f"{city_key}_{a['year']}_{a['type']}"
            filename = f"{a['year']}_{a['type']}.pdf"

            # Count amendment markers from ingestion manifest if available
            manifest_path = os.path.join(AMENDMENT_DIR, city_key, "ingestion_manifest.json")
            amendment_count = 0
            pages_count = 0
            if os.path.exists(manifest_path):
                with open(manifest_path) as f:
                    manifest = json.load(f)
                for entry in manifest:
                    if entry.get("source_file") == filename:
                        amendment_count = len(entry.get("amendment_markers", []))
                        pages_count = entry.get("pages_count", 0)
                        break

            session.run(
                "MERGE (ad:AmendmentDoc {doc_id: $doc_id}) "
                "SET ad.year = $year, ad.type = $type, ad.filename = $filename, "
                "    ad.amendment_count = $amendment_count, ad.pages = $pages_count "
                "WITH ad "
                "MATCH (c:City {name: $city}) "
                "MERGE (c)-[:ADOPTED {year: $year}]->(ad) "
                "WITH ad "
                "MATCH (mc:ModelCode {edition: $edition}) "
                "MERGE (ad)-[:BASED_ON]->(mc)",
                doc_id=doc_id, year=a["year"], type=a["type"],
                filename=filename, city=city_key, edition=a["edition"],
                amendment_count=amendment_count, pages_count=pages_count,
            )
            total += 1
    print(f"Created {total} AmendmentDoc nodes with ADOPTED and BASED_ON relationships.")


def seed_code_sections(session):
    """Extract section references from amendment markers and create CodeSection nodes."""
    section_pattern = re.compile(r"(?:Section|Sec\.)\s+(\d+[A-Z]?(?:\.\d+)*)", re.IGNORECASE)

    total_sections = 0
    for city_key in CITIES:
        manifest_path = os.path.join(AMENDMENT_DIR, city_key, "ingestion_manifest.json")
        if not os.path.exists(manifest_path):
            continue

        with open(manifest_path) as f:
            manifest = json.load(f)

        for entry in manifest:
            doc_id = f"{city_key}_{entry.get('code_edition', '').split('_')[0] if entry.get('code_edition') else 'unknown'}_{entry.get('source_file', '').split('_')[0]}"
            # Try to match with ADOPTIONS
            filename = entry.get("source_file", "")
            year_match = re.match(r"(\d{4})_", filename)
            if not year_match:
                continue
            year = year_match.group(1)
            type_match = re.search(r"_(BC|RC|Whole)\.", filename)
            doc_type = type_match.group(1) if type_match else "Whole"
            doc_id = f"{city_key}_{year}_{doc_type}"

            markers = entry.get("amendment_markers", [])
            sections = set()
            for marker in markers:
                for match in section_pattern.finditer(str(marker)):
                    sections.add(match.group(1))

            for section_ref in sections:
                session.run(
                    "MERGE (cs:CodeSection {ref: $ref}) "
                    "WITH cs "
                    "MATCH (ad:AmendmentDoc {doc_id: $doc_id}) "
                    "MERGE (ad)-[:AMENDS]->(cs)",
                    ref=section_ref, doc_id=doc_id,
                )
                total_sections += 1

    print(f"Created CodeSection nodes with {total_sections} AMENDS relationships.")


def create_cross_jurisdiction_links(session):
    """Create SAME_SECTION relationships between cities that amend the same code section."""
    result = session.run(
        "MATCH (c1:City)-[:ADOPTED]->(ad1:AmendmentDoc)-[:AMENDS]->(cs:CodeSection)<-[:AMENDS]-(ad2:AmendmentDoc)<-[:ADOPTED]-(c2:City) "
        "WHERE c1.name < c2.name "
        "WITH cs, c1, c2, count(*) AS shared_count "
        "MERGE (c1)-[r:SHARES_AMENDED_SECTION]->(c2) "
        "SET r.section = cs.ref, r.count = shared_count "
        "RETURN count(r) AS links_created"
    )
    count = result.single()["links_created"]
    print(f"Created {count} cross-jurisdiction SHARES_AMENDED_SECTION links.")


def print_summary(session):
    """Print graph summary."""
    print("\n" + "=" * 60)
    print("KNOWLEDGE GRAPH SUMMARY")
    print("=" * 60)

    queries = [
        ("Cities", "MATCH (c:City) RETURN count(c) AS c"),
        ("States", "MATCH (s:State) RETURN count(s) AS c"),
        ("Model Codes", "MATCH (mc:ModelCode) RETURN count(mc) AS c"),
        ("Amendment Docs", "MATCH (ad:AmendmentDoc) RETURN count(ad) AS c"),
        ("Code Sections", "MATCH (cs:CodeSection) RETURN count(cs) AS c"),
        ("ADOPTED rels", "MATCH ()-[r:ADOPTED]->() RETURN count(r) AS c"),
        ("BASED_ON rels", "MATCH ()-[r:BASED_ON]->() RETURN count(r) AS c"),
        ("AMENDS rels", "MATCH ()-[r:AMENDS]->() RETURN count(r) AS c"),
        ("SHARES_AMENDED_SECTION rels", "MATCH ()-[r:SHARES_AMENDED_SECTION]->() RETURN count(r) AS c"),
    ]

    for label, query in queries:
        result = session.run(query)
        print(f"  {label}: {result.single()['c']}")

    # Show cities and their adoption counts
    print("\nCity adoption timeline:")
    result = session.run(
        "MATCH (c:City)-[r:ADOPTED]->(ad:AmendmentDoc) "
        "RETURN c.display_name AS city, count(ad) AS docs, "
        "       min(ad.year) AS first_year, max(ad.year) AS latest_year "
        "ORDER BY docs DESC"
    )
    for record in result:
        print(f"  {record['city']}: {record['docs']} docs ({record['first_year']}-{record['latest_year']})")


def main():
    print("Connecting to Neo4j Aura...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # Clear existing data
        print("Clearing existing data...")
        session.run("MATCH (n) DETACH DELETE n")

        # Build graph
        create_schema(session)
        seed_states(session)
        seed_model_codes(session)
        seed_cities(session)
        seed_amendment_docs(session)
        seed_code_sections(session)
        create_cross_jurisdiction_links(session)
        print_summary(session)

    driver.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
