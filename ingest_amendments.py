"""
Multi-City Amendment Ingestion Pipeline

Handles the core challenges of building code amendment data:
1. Different PDF formats per jurisdiction (UpCodes, Municode, scanned docs)
2. Table-heavy amendment documents
3. Images, icons, and amendment markers
4. Varying text layouts and structures across cities/counties

Architecture:
  PDF → detect_format() → extract_text() → identify_amendments() → chunk → embed → store
"""

import os
import re
import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional

# Canonical city name mapping — all variants resolve to proper-cased names with spaces
CANONICAL_CITIES = {
    "losangeles": "Los Angeles", "los angeles": "Los Angeles",
    "sandiego": "San Diego", "san diego": "San Diego",
    "santaclarita": "Santa Clarita", "santa clarita": "Santa Clarita",
    "phoenix": "Phoenix", "henderson": "Henderson", "irvine": "Irvine",
    "reno": "Reno", "scottsdale": "Scottsdale", "atlanta": "Atlanta",
}


def normalize_city(name: str) -> str:
    """Normalize city name to canonical form with proper spacing."""
    return CANONICAL_CITIES.get(name.lower().strip(), name)

import httpx
import pdfplumber
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ─── Configuration ────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=OPENAI_KEY)
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)


# ─── Data Types ───────────────────────────────────────────────────────────────


@dataclass
class AmendmentRecord:
    """A structured record of a building code amendment or code section."""
    city: str
    state: str
    jurisdiction_type: str  # "city", "county", "state"
    code_title: str  # e.g., "Building Code", "Fire Code"
    code_edition: str  # e.g., "2019", "2021"
    chapter: str  # e.g., "Chapter 7", "Section 1613"
    chapter_title: str  # e.g., "Fire and Smoke Protection Features"
    source_format: str  # "upcodes", "municode", "scanned", "html"
    source_file: str
    has_local_amendments: bool = False
    amendment_markers: list = field(default_factory=list)
    tables_count: int = 0
    images_count: int = 0
    pages_count: int = 0
    content_hash: str = ""


@dataclass
class ExtractedPage:
    """A single page extracted from a PDF with format-aware processing."""
    page_num: int
    text: str
    tables: list = field(default_factory=list)
    images_count: int = 0
    has_amendment_marker: bool = False
    amendment_sections: list = field(default_factory=list)


# ─── Format Detection ────────────────────────────────────────────────────────


def detect_pdf_format(pdf_path: str) -> str:
    """Detect the source format of a building code PDF.

    Different jurisdictions publish codes in different formats:
    - UpCodes: web-scraped, has headers/footers with "upcodes" URL
    - Municode: structured legal format with ordinance numbers
    - Scanned: image-based, needs OCR (low text extraction)
    - Standard: clean text PDF
    """
    filename = os.path.basename(pdf_path).lower()

    if "upcodes" in filename or "up.codes" in filename:
        return "upcodes"

    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) == 0:
            return "empty"

        # Sample first 3 pages
        sample_text = ""
        total_images = 0
        for page in pdf.pages[:3]:
            text = page.extract_text() or ""
            sample_text += text
            total_images += len(page.images or [])

        sample_lower = sample_text.lower()

        if "upcodes" in sample_lower or "up.codes" in sample_lower:
            return "upcodes"
        if "municode" in sample_lower or "ordinance no." in sample_lower:
            return "municode"
        if len(sample_text.strip()) < 100 and total_images > 3:
            return "scanned"  # mostly images, little text → likely scanned
        return "standard"


# ─── Amendment Detection ──────────────────────────────────────────────────────

# Patterns that indicate local amendments vs. base model code
AMENDMENT_PATTERNS = [
    r"\[LAMC\]",  # Los Angeles Municipal Code marker
    r"\[SFM\]",  # State Fire Marshal
    r"\[DPH\]",  # Department of Public Health
    r"\[SLC\]",  # State Lands Commission
    r"\[BSC\]",  # Building Standards Commission
    r"\[HCD\]",  # Housing and Community Development
    r"(?:Section|Sec\.)\s+\d+[A-Z]?\.\d+",  # Section references with amendment suffix (e.g., 16A)
    r"(?:Amended|Added|Repealed)\s+by\s+Ord",  # Ordinance amendment markers
    r"Ord\.\s+No\.\s+\d+",  # Ordinance number references
    r"EXCEPTION:",  # Local exceptions to model code
    r"LOCAL AMENDMENT",  # Explicit amendment marker
    r"amended\s+\d{1,2}/\d{1,2}/\d{2,4}",  # Amendment dates
]

AMENDMENT_RE = re.compile("|".join(AMENDMENT_PATTERNS), re.IGNORECASE)


def detect_amendments_in_text(text: str) -> list:
    """Find amendment markers in text content."""
    markers = []
    for match in AMENDMENT_RE.finditer(text):
        markers.append({
            "marker": match.group(),
            "position": match.start(),
            "context": text[max(0, match.start() - 50) : match.end() + 50].strip(),
        })
    return markers


# ─── Text Extraction (Format-Aware) ──────────────────────────────────────────


def extract_upcodes_page(page) -> ExtractedPage:
    """Extract from UpCodes-format PDF with header/footer removal."""
    text = page.extract_text() or ""

    # Remove UpCodes header/footer lines
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line_lower = line.strip().lower()
        # Skip UpCodes navigation/header lines
        if any(skip in line_lower for skip in [
            "upcodes", "up.codes", "https://up.codes",
            "table of contents", "print page",
        ]):
            continue
        # Skip timestamp headers (e.g., "2/9/26, 9:36 PM")
        if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}", line.strip()):
            continue
        cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines).strip()

    # Extract tables
    tables = []
    for table in (page.extract_tables() or []):
        table_rows = []
        for row in table:
            if any(cell for cell in row):
                table_rows.append(" | ".join(str(cell or "").strip() for cell in row))
        if table_rows:
            tables.append("\n".join(table_rows))

    # Detect amendments
    amendments = detect_amendments_in_text(cleaned_text)

    return ExtractedPage(
        page_num=page.page_number,
        text=cleaned_text,
        tables=tables,
        images_count=len(page.images or []),
        has_amendment_marker=len(amendments) > 0,
        amendment_sections=[a["marker"] for a in amendments],
    )


def extract_standard_page(page) -> ExtractedPage:
    """Extract from standard PDF format."""
    text = page.extract_text() or ""

    tables = []
    for table in (page.extract_tables() or []):
        table_rows = []
        for row in table:
            if any(cell for cell in row):
                table_rows.append(" | ".join(str(cell or "").strip() for cell in row))
        if table_rows:
            tables.append("\n".join(table_rows))

    amendments = detect_amendments_in_text(text)

    return ExtractedPage(
        page_num=page.page_number,
        text=text,
        tables=tables,
        images_count=len(page.images or []),
        has_amendment_marker=len(amendments) > 0,
        amendment_sections=[a["marker"] for a in amendments],
    )


def extract_pdf(pdf_path: str, source_format: str) -> list:
    """Extract all pages from a PDF with format-aware processing."""
    pages = []
    extractor = extract_upcodes_page if source_format == "upcodes" else extract_standard_page

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted = extractor(page)
            if extracted.text.strip() or extracted.tables:
                pages.append(extracted)

    return pages


# ─── Metadata Extraction ─────────────────────────────────────────────────────


def parse_filename_metadata(filename: str) -> dict:
    """Extract city, chapter, and code info from filename patterns."""
    meta = {"city": "Unknown", "state": "Unknown", "chapter": "", "chapter_title": "", "code_edition": ""}

    # UpCodes pattern: "Chapter X Title_ City Building Code Year _ UpCodes.pdf"
    upcodes_match = re.match(
        r"((?:Chapter|Appendix)\s+\S+)\s+(.+?)_\s*(.+?)\s+(?:City\s+)?Building Code\s+(\d{4})",
        filename,
    )
    if upcodes_match:
        meta["chapter"] = upcodes_match.group(1).strip()
        meta["chapter_title"] = upcodes_match.group(2).strip()
        city_part = upcodes_match.group(3).strip()
        meta["code_edition"] = upcodes_match.group(4)
        # Parse city from "Los Angeles City" or "City of Houston"
        meta["city"] = normalize_city(city_part.replace(" City", "").strip())
        # Infer state from known cities
        city_state_map = {
            "Los Angeles": "CA", "San Francisco": "CA", "San Diego": "CA",
            "Houston": "TX", "Dallas": "TX", "Austin": "TX",
            "Phoenix": "AZ", "Miami": "FL", "Atlanta": "GA", "Boston": "MA",
            "Chicago": "IL", "New York": "NY", "Seattle": "WA", "Denver": "CO",
        }
        meta["state"] = city_state_map.get(meta["city"], "Unknown")
        return meta

    # Municode pattern: "City of X - Ordinance Y"
    municode_match = re.match(r"City of (\w+)", filename)
    if municode_match:
        meta["city"] = normalize_city(municode_match.group(1))

    return meta


# ─── Chunking with Amendment Context ─────────────────────────────────────────


def build_chunks_with_context(pages: list, record: AmendmentRecord) -> list:
    """Build text chunks that preserve amendment context and table structure.

    Each chunk includes:
    - The text content
    - Any tables on that page (formatted for readability)
    - Amendment markers if present
    - Image notes if images exist
    """
    all_parts = []

    for page in pages:
        parts = []

        # Add text
        if page.text.strip():
            parts.append(page.text)

        # Add tables with markers
        for table in page.tables:
            parts.append(f"[TABLE]\n{table}\n[/TABLE]")

        # Note images
        if page.images_count > 0:
            parts.append(
                f"[NOTE: Page {page.page_num} contains {page.images_count} image(s)/icon(s) "
                f"that may include diagrams, amendment markers, or compliance symbols]"
            )

        # Note amendment markers
        if page.amendment_sections:
            parts.append(
                f"[AMENDMENT MARKERS: {', '.join(page.amendment_sections)}]"
            )

        if parts:
            all_parts.append("\n\n".join(parts))

    # Combine and split
    full_text = "\n\n---\n\n".join(all_parts)
    chunks = splitter.split_text(full_text)

    return chunks


# ─── Supabase Upload ─────────────────────────────────────────────────────────


def upload_chunks(chunks: list, record: AmendmentRecord) -> int:
    """Embed and upload chunks to Supabase with structured metadata."""
    batch_size = 20
    total = 0

    metadata_base = {
        "city": record.city,
        "state": record.state,
        "jurisdiction_type": record.jurisdiction_type,
        "code_title": record.code_title,
        "code_edition": record.code_edition,
        "chapter": record.chapter,
        "chapter_title": record.chapter_title,
        "source_format": record.source_format,
        "original_filename": record.source_file,
        "has_local_amendments": record.has_local_amendments,
    }

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        batch_embeddings = embeddings.embed_documents(batch)

        rows = []
        for chunk_text, embedding in zip(batch, batch_embeddings):
            rows.append({
                "content": chunk_text,
                "metadata": {**metadata_base, "chunk_index": i + len(rows)},
                "embedding": embedding,
            })

        res = httpx.post(
            f"{SUPABASE_URL}/rest/v1/documents",
            headers=HEADERS,
            json=rows,
            timeout=60,
        )

        if res.status_code in (200, 201):
            total += len(batch)
        else:
            print(f"    ERROR uploading batch: {res.status_code} - {res.text[:200]}")

    return total


# ─── Main Pipeline ────────────────────────────────────────────────────────────


def ingest_pdf(pdf_path: str, city: str = None, state: str = None) -> AmendmentRecord:
    """Full ingestion pipeline for a single PDF.

    1. Detect format (UpCodes, Municode, scanned, standard)
    2. Extract text with format-aware processing
    3. Detect amendment markers
    4. Chunk with context preservation
    5. Embed and upload to vector store
    """
    filename = os.path.basename(pdf_path)
    print(f"\n{'='*60}")
    print(f"Processing: {filename}")

    # Step 1: Detect format
    source_format = detect_pdf_format(pdf_path)
    print(f"  Format: {source_format}")

    # Step 2: Parse metadata from filename
    meta = parse_filename_metadata(filename)
    if city:
        meta["city"] = normalize_city(city)
    if state:
        meta["state"] = state

    # Step 3: Extract pages
    pages = extract_pdf(pdf_path, source_format)
    print(f"  Extracted: {len(pages)} pages")

    # Step 4: Analyze amendments
    total_amendments = sum(len(p.amendment_sections) for p in pages)
    total_tables = sum(len(p.tables) for p in pages)
    total_images = sum(p.images_count for p in pages)
    amendment_pages = sum(1 for p in pages if p.has_amendment_marker)

    print(f"  Amendment markers: {total_amendments} across {amendment_pages} pages")
    print(f"  Tables: {total_tables}, Images: {total_images}")

    # Step 5: Create record
    content_hash = hashlib.md5(
        "".join(p.text for p in pages).encode()
    ).hexdigest()[:12]

    record = AmendmentRecord(
        city=meta["city"],
        state=meta["state"],
        jurisdiction_type="city",
        code_title="Building Code",
        code_edition=meta.get("code_edition", ""),
        chapter=meta.get("chapter", ""),
        chapter_title=meta.get("chapter_title", ""),
        source_format=source_format,
        source_file=filename,
        has_local_amendments=total_amendments > 0,
        amendment_markers=[m for p in pages for m in p.amendment_sections],
        tables_count=total_tables,
        images_count=total_images,
        pages_count=len(pages),
        content_hash=content_hash,
    )

    # Step 6: Build chunks
    chunks = build_chunks_with_context(pages, record)
    print(f"  Chunks: {len(chunks)}")

    # Step 7: Upload
    uploaded = upload_chunks(chunks, record)
    print(f"  Uploaded: {uploaded} chunks")

    return record


def ingest_directory(
    directory: str,
    city: str = None,
    state: str = None,
    file_filter: str = None,
) -> list:
    """Ingest all PDFs from a directory.

    Args:
        directory: Path to directory containing PDFs
        city: Override city name for all files
        state: Override state for all files
        file_filter: Only process files containing this string
    """
    pdfs = sorted(
        f for f in os.listdir(directory) if f.lower().endswith(".pdf")
    )
    if file_filter:
        pdfs = [f for f in pdfs if file_filter.lower() in f.lower()]

    print(f"\nFound {len(pdfs)} PDFs in {directory}")
    records = []

    for pdf_name in pdfs:
        pdf_path = os.path.join(directory, pdf_name)
        try:
            record = ingest_pdf(pdf_path, city=city, state=state)
            records.append(record)
        except Exception as e:
            print(f"  ERROR processing {pdf_name}: {e}")

    # Summary
    print(f"\n{'='*60}")
    print(f"INGESTION SUMMARY")
    print(f"  Total files: {len(records)}")
    print(f"  Total pages: {sum(r.pages_count for r in records)}")
    print(f"  Files with amendments: {sum(1 for r in records if r.has_local_amendments)}")
    print(f"  Total tables: {sum(r.tables_count for r in records)}")
    print(f"  Total images: {sum(r.images_count for r in records)}")

    # Save manifest
    manifest_path = os.path.join(directory, "ingestion_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump([asdict(r) for r in records], f, indent=2)
    print(f"  Manifest saved: {manifest_path}")

    return records


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ingest_amendments.py <directory> [city] [state] [filter]")
        print("")
        print("Examples:")
        print("  python ingest_amendments.py ./2019_Building 'Los Angeles' CA")
        print("  python ingest_amendments.py ./2019_Building 'Los Angeles' CA 'Chapter 7'")
        print("  python ingest_amendments.py ./houston_codes Houston TX")
        sys.exit(1)

    directory = sys.argv[1]
    city = sys.argv[2] if len(sys.argv) > 2 else None
    state = sys.argv[3] if len(sys.argv) > 3 else None
    file_filter = sys.argv[4] if len(sys.argv) > 4 else None

    ingest_directory(directory, city=city, state=state, file_filter=file_filter)
