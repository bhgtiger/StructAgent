"""Shared utilities for Semantic Scholar API tools."""

import json
import os
import sys
import time
from pathlib import Path

import requests

API_BASE = "https://api.semanticscholar.org/graph/v1"
REC_BASE = "https://api.semanticscholar.org/recommendations/v1"
RATE_LIMIT_DELAY = 1.05  # slightly over 1 req/s for free tier

# Standard fields we always want for paper results
STANDARD_FIELDS = (
    "paperId,title,year,abstract,citationCount,influentialCitationCount,"
    "publicationTypes,publicationDate,openAccessPdf,authors,venue,externalIds"
)

# Compact fields for bulk/light queries
COMPACT_FIELDS = (
    "paperId,title,year,citationCount,publicationTypes,publicationDate,"
    "openAccessPdf,authors,venue"
)


def get_api_key() -> str | None:
    """Load S2 API key from env or file."""
    key = os.environ.get("S2_API_KEY")
    if key:
        return key.strip()
    key_file = Path.home() / ".s2_api_key"
    if key_file.exists():
        return key_file.read_text().strip()
    return None


def make_headers() -> dict:
    """Build request headers with optional API key."""
    headers = {"Accept": "application/json"}
    key = get_api_key()
    if key:
        headers["x-api-key"] = key
    else:
        print("⚠️  No S2 API key found. Set S2_API_KEY or create ~/.s2_api_key", file=sys.stderr)
    return headers


def s2_get(url: str, params: dict | None = None, retries: int = 3) -> dict | None:
    """GET request with retry and rate-limit handling."""
    headers = make_headers()
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", 2))
                print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            if resp.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            return None
        except requests.RequestException as e:
            print(f"  Request error: {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
    return None


def s2_post(url: str, json_body: dict, params: dict | None = None, retries: int = 3) -> dict | None:
    """POST request with retry and rate-limit handling."""
    headers = make_headers()
    headers["Content-Type"] = "application/json"
    for attempt in range(retries):
        try:
            resp = requests.post(url, json=json_body, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", 2))
                print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            if resp.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            return None
        except requests.RequestException as e:
            print(f"  Request error: {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
    return None


def format_paper(paper: dict, compact: bool = False) -> str:
    """Format a paper dict into a human-readable string."""
    title = paper.get("title", "Untitled")
    year = paper.get("year", "?")
    cites = paper.get("citationCount", 0)
    influential = paper.get("influentialCitationCount", 0)
    venue = paper.get("venue", "")
    pid = paper.get("paperId", "")

    authors = paper.get("authors", [])
    if authors:
        if len(authors) <= 3:
            author_str = ", ".join(a.get("name", "?") for a in authors)
        else:
            author_str = f"{authors[0].get('name', '?')} et al. ({len(authors)} authors)"
    else:
        author_str = "Unknown"

    pdf = paper.get("openAccessPdf")
    pdf_str = f"  📄 {pdf['url']}" if pdf else ""

    doi = ""
    ext = paper.get("externalIds", {})
    if ext and ext.get("DOI"):
        doi = f"  DOI: {ext['DOI']}"

    pub_types = paper.get("publicationTypes", [])
    type_str = f"  [{', '.join(pub_types)}]" if pub_types else ""

    lines = [f"• {title} ({year})", f"  {author_str} — {venue}" if venue else f"  {author_str}"]
    lines.append(f"  Citations: {cites}" + (f" ({influential} influential)" if influential else ""))
    if type_str:
        lines.append(type_str)
    if doi:
        lines.append(doi)
    if pdf_str:
        lines.append(pdf_str)
    if not compact:
        abstract = paper.get("abstract", "")
        if abstract:
            lines.append(f"  Abstract: {abstract[:300]}{'...' if len(abstract) > 300 else ''}")
    lines.append(f"  ID: {pid}")
    return "\n".join(lines)


def format_tsv(paper: dict) -> str:
    """Format a paper as a TSV line."""
    title = paper.get("title", "").replace("\t", " ")
    year = paper.get("year", "")
    cites = paper.get("citationCount", 0)
    pid = paper.get("paperId", "")
    pdf = paper.get("openAccessPdf", {})
    url = pdf.get("url", "") if pdf else ""
    authors = paper.get("authors", [])
    first_author = authors[0].get("name", "") if authors else ""
    return f"{title}\t{first_author}\t{year}\t{cites}\t{url}\t{pid}"


def output_results(papers: list[dict], fmt: str = "pretty", file=sys.stdout):
    """Output paper results in the requested format."""
    if fmt == "json":
        json.dump(papers, file, indent=2, ensure_ascii=False)
        print(file=file)
    elif fmt == "tsv":
        print("title\tfirst_author\tyear\tcitations\tpdf_url\tpaper_id", file=file)
        for p in papers:
            print(format_tsv(p), file=file)
    else:  # pretty
        for i, p in enumerate(papers, 1):
            print(f"\n{'─' * 60}", file=file)
            print(f"  [{i}]", file=file)
            print(format_paper(p), file=file)
        print(f"\n{'─' * 60}", file=file)
        print(f"Total: {len(papers)} papers", file=file)
