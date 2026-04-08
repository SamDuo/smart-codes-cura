"""
Docling-Based Document Ingestion Pipeline for SmartCodes
=========================================================

Upgrades from the pdfplumber pipeline (ingest_amendments.py) with:
  - AI-based table extraction via TableFormer (IBM)
  - DocLayNet layout analysis for section/subsection detection
  - Structure-aware HybridChunker (respects document hierarchy)
  - Same Supabase upload pattern for seamless integration

Falls back to pdfplumber if docling fails to load (e.g., Python 3.14 edge cases).

Usage:
  python ingest_docling.py <directory> <city> <state>
  python ingest_docling.py ./pages/documents "Los Angeles" CA
"""

import os
import sys
import json
import hashlib
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

import httpx
from langchain_openai import OpenAIEmbeddings

# Canonical city name mapping
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

# ─── Docling Import (with pdfplumber fallback) ──────────────────────────────

USE_DOCLING = False
FALLBACK_REASON = ""

try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        TableFormerMode,
        TableStructureOptions,
    )
    from docling.datamodel.base_models import InputFormat
    from docling.chunking import HybridChunker

    USE_DOCLING = True
except Exception as e:
    FALLBACK_REASON = str(e)
    try:
        import pdfplumber
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        raise RuntimeError(
            f"Neither docling nor pdfplumber available.\n"
            f"Docling error: {e}"
        )

# ─── Configuration ──────────────────────────────────────────────────────────

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

# ─── Docling Converter Setup ───────────────────────────────────────────────

_converter = None


def get_docling_converter() -> "DocumentConverter":
    """Lazily initialise a Docling DocumentConverter with TableFormer + layout."""
    global _converter
    if _converter is not None:
        return _converter

    pipeline_opts = PdfPipelineOptions(
        do_table_structure=True,
        do_ocr=True,
        table_structure_options=TableStructureOptions(
            do_cell_matching=True,
            mode=TableFormerMode.ACCURATE,      # AI-based TableFormer
        ),
    )

    _converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_opts,
            ),
        },
    )
    return _converter


def get_hybrid_chunker() -> "HybridChunker":
    """Create a HybridChunker that respects document structure.

    Uses the default sentence-transformers tokenizer (all-MiniLM-L6-v2)
    with merge_peers=True so adjacent same-level sections are combined
    into fuller chunks rather than being split at every heading.
    """
    return HybridChunker(
        merge_peers=True,
    )


# ─── Amendment Detection (shared with ingest_amendments.py) ────────────────

AMENDMENT_PATTERNS = [
    r"\[LAMC\]", r"\[SFM\]", r"\[DPH\]", r"\[SLC\]", r"\[BSC\]", r"\[HCD\]",
    r"(?:Section|Sec\.)\s+\d+[A-Z]?\.\d+",
    r"(?:Amended|Added|Repealed)\s+by\s+Ord",
    r"Ord\.\s+No\.\s+\d+",
    r"EXCEPTION:",
    r"LOCAL AMENDMENT",
    r"amended\s+\d{1,2}/\d{1,2}/\d{2,4}",
]
AMENDMENT_RE = re.compile("|".join(AMENDMENT_PATTERNS), re.IGNORECASE)


def detect_amendments_in_text(text: str) -> list[dict]:
    markers = []
    for match in AMENDMENT_RE.finditer(text):
        markers.append({
            "marker": match.group(),
            "position": match.start(),
            "context": text[max(0, match.start() - 50): match.end() + 50].strip(),
        })
    return markers


# ─── Docling-Based Extraction ──────────────────────────────────────────────


@dataclass
class DoclingResult:
    """Result of docling-based PDF processing."""
    filename: str
    page_count: int
    chunks: list[str]
    tables_count: int
    amendment_markers: list[str]
    has_local_amendments: bool
    export_md: str   # full Markdown export for LightRAG


def extract_with_docling(pdf_path: str) -> DoclingResult:
    """Parse a PDF with Docling and produce structure-aware chunks."""
    converter = get_docling_converter()
    chunker = get_hybrid_chunker()

    # Convert PDF -> DoclingDocument
    result = converter.convert(pdf_path)
    dl_doc = result.document

    # Export full Markdown (useful for LightRAG ingestion later)
    export_md = dl_doc.export_to_markdown()

    # Count pages from the conversion metadata
    page_count = 0
    if hasattr(result, "pages") and result.pages:
        page_count = len(result.pages)
    elif hasattr(dl_doc, "pages") and dl_doc.pages:
        page_count = len(dl_doc.pages)

    # Count tables
    tables_count = 0
    if hasattr(dl_doc, "tables"):
        tables_count = len(dl_doc.tables)

    # Structure-aware chunking
    chunks = []
    for chunk in chunker.chunk(dl_doc):
        text = chunk.text if hasattr(chunk, "text") else str(chunk)
        if text.strip():
            chunks.append(text)

    # Detect amendments across all chunks
    all_markers = []
    for chunk_text in chunks:
        markers = detect_amendments_in_text(chunk_text)
        all_markers.extend(m["marker"] for m in markers)

    return DoclingResult(
        filename=os.path.basename(pdf_path),
        page_count=page_count,
        chunks=chunks,
        tables_count=tables_count,
        amendment_markers=all_markers,
        has_local_amendments=len(all_markers) > 0,
        export_md=export_md,
    )


# ─── pdfplumber Fallback Extraction ──────────────────────────────────────

def extract_with_pdfplumber(pdf_path: str) -> DoclingResult:
    """Fallback extraction when docling is unavailable."""
    import pdfplumber
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)

    page_texts = []
    tables_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            parts = []

            # Tables
            tables = page.extract_tables() or []
            for table in tables:
                table_text = "\n".join(
                    " | ".join(str(cell or "") for cell in row)
                    for row in table if any(cell for cell in row)
                )
                if table_text.strip():
                    parts.append(f"[TABLE]\n{table_text}\n[/TABLE]")
                    tables_count += 1

            # Text
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)

            # Images note
            images = page.images or []
            if images:
                parts.append(
                    f"[NOTE: Page contains {len(images)} image(s)/icon(s)]"
                )

            combined = "\n\n".join(parts)
            if combined.strip():
                page_texts.append(combined)

    full_text = "\n\n---\n\n".join(page_texts)
    chunks = splitter.split_text(full_text) if full_text.strip() else []

    # Detect amendments
    all_markers = []
    for chunk_text in chunks:
        markers = detect_amendments_in_text(chunk_text)
        all_markers.extend(m["marker"] for m in markers)

    return DoclingResult(
        filename=os.path.basename(pdf_path),
        page_count=page_count,
        chunks=chunks,
        tables_count=tables_count,
        amendment_markers=all_markers,
        has_local_amendments=len(all_markers) > 0,
        export_md=full_text,
    )


# ─── Supabase Upload ───────────────────────────────────────────────────────


def upload_chunks(
    chunks: list[str],
    metadata_base: dict,
    batch_size: int = 20,
) -> int:
    """Embed and upload chunks to Supabase with structured metadata."""
    total = 0

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i: i + batch_size]
        batch_embeddings = embeddings.embed_documents(batch)

        rows = []
        for j, (chunk_text, embedding) in enumerate(zip(batch, batch_embeddings)):
            rows.append({
                "content": chunk_text,
                "metadata": {**metadata_base, "chunk_index": i + j},
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


# ─── Markdown Export (for LightRAG) ────────────────────────────────────────

def save_markdown_export(result: DoclingResult, output_dir: str) -> str:
    """Save the Markdown export to disk so LightRAG can index it later."""
    os.makedirs(output_dir, exist_ok=True)
    safe_name = re.sub(r"[^\w\-.]", "_", result.filename.rsplit(".", 1)[0])
    md_path = os.path.join(output_dir, f"{safe_name}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result.export_md)
    return md_path


# ─── Main Pipeline ─────────────────────────────────────────────────────────


def ingest_pdf(
    pdf_path: str,
    city: str = "Unknown",
    state: str = "Unknown",
    save_md: bool = True,
) -> dict:
    """Full ingestion pipeline for a single PDF using Docling (or fallback).

    Returns a summary dict with ingestion stats.
    """
    filename = os.path.basename(pdf_path)
    print(f"\n{'=' * 60}")
    print(f"Processing: {filename}")

    backend = "docling" if USE_DOCLING else "pdfplumber"
    print(f"  Backend: {backend}")
    if not USE_DOCLING:
        print(f"  Fallback reason: {FALLBACK_REASON}")

    # Extract
    if USE_DOCLING:
        result = extract_with_docling(pdf_path)
    else:
        result = extract_with_pdfplumber(pdf_path)

    print(f"  Pages: {result.page_count}")
    print(f"  Tables: {result.tables_count}")
    print(f"  Chunks: {len(result.chunks)}")
    print(f"  Amendment markers: {len(result.amendment_markers)}")

    # Save Markdown for LightRAG
    if save_md:
        md_dir = os.path.join(os.path.dirname(pdf_path), "..", "data", "parsed")
        md_path = save_markdown_export(result, md_dir)
        print(f"  Markdown saved: {md_path}")

    # Build metadata
    metadata_base = {
        "city": normalize_city(city),
        "state": state,
        "jurisdiction_type": "city",
        "code_title": "Building Code",
        "original_filename": filename,
        "source": backend,
        "has_local_amendments": result.has_local_amendments,
        "tables_count": result.tables_count,
        "pages_count": result.page_count,
    }

    # Upload to Supabase
    uploaded = upload_chunks(result.chunks, metadata_base)
    print(f"  Uploaded: {uploaded} chunks to Supabase")

    return {
        "filename": filename,
        "backend": backend,
        "pages": result.page_count,
        "tables": result.tables_count,
        "chunks": len(result.chunks),
        "uploaded": uploaded,
        "amendments": len(result.amendment_markers),
        "has_local_amendments": result.has_local_amendments,
    }


def ingest_directory(
    directory: str,
    city: str = "Unknown",
    state: str = "Unknown",
) -> list[dict]:
    """Ingest all PDFs from a directory.

    Args:
        directory: Path to directory containing PDFs.
        city: City name applied to all files.
        state: State abbreviation applied to all files.
    """
    pdfs = sorted(
        f for f in os.listdir(directory) if f.lower().endswith(".pdf")
    )
    print(f"\nFound {len(pdfs)} PDFs in {directory}")
    print(f"Backend: {'docling (TableFormer + DocLayNet)' if USE_DOCLING else 'pdfplumber (fallback)'}")

    results = []
    for pdf_name in pdfs:
        pdf_path = os.path.join(directory, pdf_name)
        try:
            summary = ingest_pdf(pdf_path, city=city, state=state)
            results.append(summary)
        except Exception as e:
            print(f"  ERROR processing {pdf_name}: {e}")
            results.append({"filename": pdf_name, "error": str(e)})

    # Summary
    successful = [r for r in results if "error" not in r]
    print(f"\n{'=' * 60}")
    print("INGESTION SUMMARY")
    print(f"  Backend: {'docling' if USE_DOCLING else 'pdfplumber'}")
    print(f"  Total files: {len(results)} ({len(successful)} succeeded)")
    print(f"  Total pages: {sum(r.get('pages', 0) for r in successful)}")
    print(f"  Total chunks: {sum(r.get('chunks', 0) for r in successful)}")
    print(f"  Total uploaded: {sum(r.get('uploaded', 0) for r in successful)}")
    print(f"  Files with amendments: {sum(1 for r in successful if r.get('has_local_amendments'))}")
    print(f"  Total tables: {sum(r.get('tables', 0) for r in successful)}")

    # Save manifest
    manifest_path = os.path.join(directory, "docling_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Manifest saved: {manifest_path}")

    return results


# ─── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_docling.py <directory> [city] [state]")
        print("")
        print("Examples:")
        print("  python ingest_docling.py ./pages/documents 'Los Angeles' CA")
        print("  python ingest_docling.py /path/to/pdfs Houston TX")
        print("")
        print(f"Backend: {'docling' if USE_DOCLING else 'pdfplumber (fallback)'}")
        sys.exit(1)

    directory = sys.argv[1]
    city = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
    state = sys.argv[3] if len(sys.argv) > 3 else "Unknown"

    ingest_directory(directory, city=city, state=state)
