"""Re-ingest PDFs with pdfplumber for cleaner text extraction."""
import os
import re
import json
import httpx
import pdfplumber
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

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


def parse_city_from_filename(filename: str) -> str:
    """Extract and normalize city name from PDF filename."""
    # UpCodes: "Chapter X Title_ City Building Code Year _ UpCodes.pdf"
    m = re.search(r"_\s*(.+?)\s+(?:City\s+)?Building Code", filename)
    if m:
        return normalize_city(m.group(1).replace(" City", "").strip())
    # Year_Whole.pdf or Year_BC.pdf style (city from parent dir or default)
    return "Unknown"

# Config
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

DOCS_DIR = os.path.join(os.path.dirname(__file__), "pages", "documents")

embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=OPENAI_KEY)
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)


def clear_existing_docs():
    """Delete all existing documents from Supabase."""
    print("Clearing existing documents...")
    res = httpx.delete(
        f"{SUPABASE_URL}/rest/v1/documents?id=gt.00000000-0000-0000-0000-000000000000",
        headers={**HEADERS, "Prefer": "return=minimal"},
        timeout=30,
    )
    # Delete all rows
    res = httpx.delete(
        f"{SUPABASE_URL}/rest/v1/documents?id=neq.null",
        headers=HEADERS,
        timeout=60,
    )
    print(f"  Delete status: {res.status_code}")


def extract_text_pdfplumber(pdf_path):
    """Extract clean text from PDF using pdfplumber with table + image awareness."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            parts = []

            # Extract tables separately for structured data
            tables = page.extract_tables() or []
            for table in tables:
                table_text = "\n".join(
                    " | ".join(str(cell or "") for cell in row)
                    for row in table
                    if any(cell for cell in row)
                )
                if table_text.strip():
                    parts.append(f"[TABLE]\n{table_text}\n[/TABLE]")

            # Extract main text
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)

            # Note images on the page (icons, diagrams, figures)
            images = page.images or []
            if images:
                parts.append(f"[NOTE: This page contains {len(images)} image(s)/icon(s) that may include diagrams, symbols, or amendment markers]")

            combined = "\n\n".join(parts)
            if combined.strip():
                pages.append({"page": i + 1, "text": combined})
    return pages


def ingest_pdf(pdf_path):
    """Ingest a single PDF into Supabase."""
    filename = os.path.basename(pdf_path)
    print(f"\nProcessing: {filename}")

    # Extract text
    pages = extract_text_pdfplumber(pdf_path)
    print(f"  Extracted {len(pages)} pages")

    # Combine pages and split into chunks
    full_text = "\n\n".join(p["text"] for p in pages)
    chunks = splitter.split_text(full_text)
    print(f"  Split into {len(chunks)} chunks")

    # Embed and upload in batches
    batch_size = 20
    total_uploaded = 0

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        batch_embeddings = embeddings.embed_documents(batch)

        city = parse_city_from_filename(filename)
        rows = []
        for chunk_text, embedding in zip(batch, batch_embeddings):
            rows.append(
                {
                    "content": chunk_text,
                    "metadata": {"original_filename": filename, "source": "pdfplumber", "city": city},
                    "embedding": embedding,
                }
            )

        res = httpx.post(
            f"{SUPABASE_URL}/rest/v1/documents",
            headers=HEADERS,
            json=rows,
            timeout=60,
        )

        if res.status_code in (200, 201):
            total_uploaded += len(batch)
            print(f"  Uploaded batch {i // batch_size + 1}: {len(batch)} chunks (total: {total_uploaded})")
        else:
            print(f"  ERROR uploading batch: {res.status_code} - {res.text[:200]}")

    print(f"  Done: {total_uploaded} chunks uploaded for {filename}")
    return total_uploaded


def main():
    # Clear old garbled data
    clear_existing_docs()

    # Find all PDFs
    pdfs = [f for f in os.listdir(DOCS_DIR) if f.lower().endswith(".pdf")]
    print(f"\nFound {len(pdfs)} PDFs to ingest:")
    for p in pdfs:
        print(f"  - {p}")

    total = 0
    for pdf_name in pdfs:
        pdf_path = os.path.join(DOCS_DIR, pdf_name)
        total += ingest_pdf(pdf_path)

    print(f"\n=== INGESTION COMPLETE: {total} total chunks uploaded ===")


if __name__ == "__main__":
    main()
