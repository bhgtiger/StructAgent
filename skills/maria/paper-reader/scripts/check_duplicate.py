#!/usr/bin/env python3
"""
check_duplicate.py — Pre-read duplicate check against the paper database.

Extracts title from PDF page 1 (cheap), then fuzzy-matches against
all titles in database.yaml. Exits with code 0 if no duplicate found,
code 1 if a likely duplicate exists (prints match details).

Usage:
    python3 check_duplicate.py <pdf_path> <database_yaml_path>

Exit codes:
    0 — no duplicate found, safe to read
    1 — likely duplicate found (prints match info to stdout)
    2 — error (missing file, bad YAML, etc.)
"""

import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import fitz  # PyMuPDF
import yaml

SIMILARITY_THRESHOLD = 0.75  # title similarity ratio to flag as duplicate


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation/whitespace, collapse spaces."""
    t = title.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extract_title_from_pdf(pdf_path: str) -> str | None:
    """Extract title from the first page of a PDF using largest-font heuristic."""
    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        return None

    # Try PDF metadata first
    meta = doc.metadata or {}
    meta_title = meta.get("title", "").strip()

    # Extract from first page using font-size heuristic
    page = doc[0]
    blocks = []
    for b in page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]:
        if b["type"] != 0:  # text blocks only
            continue
        for line in b.get("lines", []):
            text_parts = []
            max_size = 0
            for span in line.get("spans", []):
                text_parts.append(span["text"])
                max_size = max(max_size, span["size"])
            text = " ".join(text_parts).strip()
            if text and len(text) > 3:
                blocks.append({"text": text, "font_size": max_size})

    page_title = None
    if blocks:
        max_font = max(b["font_size"] for b in blocks)
        title_blocks = [
            b for b in blocks
            if b["font_size"] >= max_font - 0.5
            and len(b["text"].split()) > 1
        ]
        if title_blocks:
            parts = []
            for b in title_blocks:
                t = b["text"].strip()
                # Stop at author-like lines
                if re.match(r"^[A-Z][a-z]+\s+[A-Z][a-z]+\s*\*?$", t):
                    break
                if "@" in t or "correspondence" in t.lower():
                    break
                parts.append(t)
            if parts:
                page_title = " ".join(parts)

    doc.close()

    # Prefer the longer of metadata vs page-extracted title
    candidates = [t for t in [meta_title, page_title] if t]
    if not candidates:
        return None
    return max(candidates, key=len)


def load_database_titles(db_path: str) -> list[dict]:
    """Load paper titles and keys from database.yaml."""
    with open(db_path) as f:
        db = yaml.safe_load(f) or {}
    papers = db.get("papers", [])
    return [
        {"key": p.get("key", ""), "title": p.get("title", ""), "id": p.get("id")}
        for p in papers
        if p.get("title")
    ]


def find_duplicate(pdf_title: str, db_papers: list[dict]) -> dict | None:
    """Return the best match above threshold, or None."""
    norm_pdf = normalize_title(pdf_title)
    best_match = None
    best_ratio = 0.0

    for paper in db_papers:
        norm_db = normalize_title(paper["title"])
        ratio = SequenceMatcher(None, norm_pdf, norm_db).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = paper

    if best_match and best_ratio >= SIMILARITY_THRESHOLD:
        return {**best_match, "similarity": round(best_ratio, 3)}
    return None


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 check_duplicate.py <pdf_path> <database_yaml_path>")
        sys.exit(2)

    pdf_path = sys.argv[1]
    db_path = sys.argv[2]

    if not Path(pdf_path).exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(2)
    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        sys.exit(2)

    # Extract title
    title = extract_title_from_pdf(pdf_path)
    if not title:
        print("Warning: could not extract title from PDF. Skipping duplicate check.")
        sys.exit(0)  # proceed with reading — can't check without a title

    print(f"Extracted title: {title}")

    # Load DB and check
    db_papers = load_database_titles(db_path)
    if not db_papers:
        print("Database is empty. No duplicates possible.")
        sys.exit(0)

    match = find_duplicate(title, db_papers)
    if match:
        print(f"\n⚠️  DUPLICATE DETECTED (similarity: {match['similarity']})")
        print(f"   Existing: [{match['key']}] {match['title']}")
        print(f"   Use --force or 're-read' to override.")
        sys.exit(1)
    else:
        print("No duplicate found. Safe to read.")
        sys.exit(0)


if __name__ == "__main__":
    main()
