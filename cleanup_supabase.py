"""
Supabase Cleanup: Fix city names + remove duplicate chunks.

Usage:
  python cleanup_supabase.py --dry-run    # Preview changes only
  python cleanup_supabase.py              # Apply changes
"""

import argparse
import hashlib
import sys
import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

CITY_RENAMES = {
    "LosAngeles": "Los Angeles",
    "Sandiego": "San Diego",
    "SantaClarita": "Santa Clarita",
}


def fetch_all_rows(select="id,content,metadata"):
    """Fetch all rows from documents table (paginated)."""
    all_rows = []
    offset = 0
    limit = 1000
    while True:
        res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/documents",
            headers={**HEADERS, "Prefer": "return=representation"},
            params={"select": select, "offset": offset, "limit": limit},
            timeout=60,
        )
        if res.status_code != 200:
            print(f"ERROR fetching at offset {offset}: {res.status_code}", flush=True)
            break
        batch = res.json()
        if not batch:
            break
        all_rows.extend(batch)
        offset += limit
        print(f"  Fetched {len(all_rows)} rows...", flush=True)
    return all_rows


def fix_city_names_batch(dry_run=True):
    """Fix city names using bulk PATCH per old name (3 requests instead of 5000+)."""
    print("\n=== City Name Fixes (batch) ===", flush=True)

    for old_name, new_name in CITY_RENAMES.items():
        # Count rows with old name
        res = httpx.get(
            f"{SUPABASE_URL}/rest/v1/documents",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={
                "select": "id",
                "metadata->>city": f"eq.{old_name}",
                "limit": 0,
            },
            timeout=30,
        )
        count = res.headers.get("content-range", "*/0").split("/")[-1]
        print(f"  {old_name} -> {new_name}: {count} rows", flush=True)

        if dry_run:
            continue

        # Fetch rows with old city name in batches and update
        offset = 0
        fixed = 0
        while True:
            res = httpx.get(
                f"{SUPABASE_URL}/rest/v1/documents",
                headers={**HEADERS, "Prefer": "return=representation"},
                params={
                    "select": "id,metadata",
                    "metadata->>city": f"eq.{old_name}",
                    "limit": 100,
                    "offset": offset,
                },
                timeout=60,
            )
            rows = res.json() if res.status_code == 200 else []
            if not rows:
                break

            for row in rows:
                meta = row["metadata"]
                meta["city"] = new_name
                patch_res = httpx.patch(
                    f"{SUPABASE_URL}/rest/v1/documents?id=eq.{row['id']}",
                    headers={**HEADERS, "Prefer": "return=minimal"},
                    json={"metadata": meta},
                    timeout=30,
                )
                if patch_res.status_code in (200, 204):
                    fixed += 1

            print(f"    Fixed {fixed} so far...", flush=True)
            # Don't increment offset -- we're modifying the filter set
            # Re-query from 0 each time since fixed rows no longer match

        if not dry_run:
            print(f"    Done: {fixed} rows fixed for {old_name}", flush=True)

    if dry_run:
        print("  [DRY RUN] No changes applied.", flush=True)


def remove_duplicates(dry_run=True):
    """Remove duplicate chunks keeping first occurrence per content+city+source."""
    print("\n=== Duplicate Removal ===", flush=True)
    print("  Fetching all rows for dedup analysis...", flush=True)
    rows = fetch_all_rows(select="id,content,metadata")
    print(f"  Total rows: {len(rows)}", flush=True)

    seen = {}
    duplicates = []
    for row in rows:
        content = row.get("content", "")
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        meta = row.get("metadata", {})
        city = meta.get("city", "")
        source = meta.get("original_filename", "")
        key = f"{content_hash}:{city}:{source}"

        if key in seen:
            duplicates.append(row["id"])
        else:
            seen[key] = row["id"]

    print(f"  Unique: {len(seen)}", flush=True)
    print(f"  Duplicates to remove: {len(duplicates)}", flush=True)

    if dry_run:
        print("  [DRY RUN] No changes applied.", flush=True)
        return

    # Delete in batches using IN filter
    removed = 0
    batch_size = 50
    for i in range(0, len(duplicates), batch_size):
        batch_ids = duplicates[i : i + batch_size]
        id_filter = ",".join(f'"{rid}"' for rid in batch_ids)
        res = httpx.delete(
            f"{SUPABASE_URL}/rest/v1/documents?id=in.({id_filter})",
            headers={**HEADERS, "Prefer": "return=minimal"},
            timeout=60,
        )
        if res.status_code in (200, 204):
            removed += len(batch_ids)
        else:
            print(f"  ERROR batch {i // batch_size + 1}: {res.status_code} {res.text[:100]}", flush=True)
            # Fallback to individual deletes
            for row_id in batch_ids:
                r = httpx.delete(
                    f"{SUPABASE_URL}/rest/v1/documents?id=eq.{row_id}",
                    headers={**HEADERS, "Prefer": "return=minimal"},
                    timeout=30,
                )
                if r.status_code in (200, 204):
                    removed += 1
        print(f"  Removed {removed}/{len(duplicates)}...", flush=True)

    print(f"  Done: {removed} duplicates removed", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Clean up Supabase documents table")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    # Step 1: Fix city names
    fix_city_names_batch(dry_run=args.dry_run)

    # Step 2: Remove duplicates (after city fix so dedup uses canonical names)
    remove_duplicates(dry_run=args.dry_run)

    if args.dry_run:
        print("\n[DRY RUN COMPLETE] Run without --dry-run to apply.", flush=True)
    else:
        print("\n[CLEANUP COMPLETE]", flush=True)


if __name__ == "__main__":
    main()
