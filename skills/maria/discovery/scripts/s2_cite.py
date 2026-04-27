#!/usr/bin/env python3
"""Explore citation and reference graphs from Semantic Scholar.

Usage:
    # Get papers that cite this paper
    python s2_cite.py 649def34f8be52c8b66281af98ae884c09aef38b --direction citations

    # Get papers referenced by this paper
    python s2_cite.py DOI:10.1038/s41586-021-03819-2 --direction references

    # Both directions
    python s2_cite.py paper_id --direction both --limit 20

    # Filter by year
    python s2_cite.py paper_id --direction citations --year 2023-
"""

import argparse
import sys
import time

from s2_common import (
    API_BASE, COMPACT_FIELDS, STANDARD_FIELDS, RATE_LIMIT_DELAY,
    s2_get, output_results, format_paper,
)


def get_citations(paper_id: str, limit: int = 20, fields: str = None) -> list[dict]:
    """Get papers that cite this paper."""
    if not fields:
        fields = COMPACT_FIELDS
    url = f"{API_BASE}/paper/{paper_id}/citations"
    params = {"fields": fields, "limit": str(min(limit, 1000))}
    data = s2_get(url, params)
    if data:
        # Citations come nested: {"citingPaper": {...}}
        return [item["citingPaper"] for item in data.get("data", []) if item.get("citingPaper")]
    return []


def get_references(paper_id: str, limit: int = 20, fields: str = None) -> list[dict]:
    """Get papers referenced by this paper."""
    if not fields:
        fields = COMPACT_FIELDS
    url = f"{API_BASE}/paper/{paper_id}/references"
    params = {"fields": fields, "limit": str(min(limit, 1000))}
    data = s2_get(url, params)
    if data:
        # References come nested: {"citedPaper": {...}}
        return [item["citedPaper"] for item in data.get("data", []) if item.get("citedPaper")]
    return []


def get_author_papers(author_id: str, limit: int = 50, fields: str = None) -> list[dict]:
    """Get all papers by an author."""
    if not fields:
        fields = COMPACT_FIELDS
    url = f"{API_BASE}/author/{author_id}/papers"
    params = {"fields": fields, "limit": str(min(limit, 1000))}
    data = s2_get(url, params)
    if data:
        return data.get("data", [])
    return []


def filter_by_year(papers: list[dict], year_spec: str) -> list[dict]:
    """Filter papers by year spec like '2020-', '2020-2023', '2023'."""
    if not year_spec:
        return papers
    if "-" in year_spec:
        parts = year_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else 9999
    else:
        start = end = int(year_spec)
    return [p for p in papers if p.get("year") and start <= p["year"] <= end]


def main():
    parser = argparse.ArgumentParser(description="Explore citation graphs via Semantic Scholar")
    parser.add_argument("paper", help="Paper ID (S2 ID or DOI:xxx format)")
    parser.add_argument("--direction", choices=["citations", "references", "both"],
                        default="both", help="Direction to explore (default: both)")
    parser.add_argument("--author", help="Author S2 ID — list their papers instead")
    parser.add_argument("--year", help="Year filter: '2020-', '2020-2023', '2023'")
    parser.add_argument("--limit", type=int, default=20, help="Max results per direction (default: 20)")
    parser.add_argument("--sort-citations", action="store_true",
                        help="Sort results by citation count (descending)")
    parser.add_argument("--full", action="store_true", help="Include abstracts")
    parser.add_argument("--format", choices=["pretty", "json", "tsv"], default="pretty",
                        help="Output format (default: pretty)")
    args = parser.parse_args()

    # Author mode
    if args.author:
        papers = get_author_papers(args.author, limit=args.limit,
                                   fields=STANDARD_FIELDS if args.full else None)
        papers = filter_by_year(papers, args.year)
        if args.sort_citations:
            papers.sort(key=lambda p: p.get("citationCount", 0), reverse=True)
        output_results(papers, args.format)
        return

    fields = STANDARD_FIELDS if args.full else None

    if args.direction in ("citations", "both"):
        citations = get_citations(args.paper, limit=args.limit, fields=fields)
        citations = filter_by_year(citations, args.year)
        if args.sort_citations:
            citations.sort(key=lambda p: p.get("citationCount", 0), reverse=True)
        if args.direction == "both":
            print(f"\n{'═' * 60}")
            print(f"  CITING PAPERS ({len(citations)})")
            print(f"{'═' * 60}")
        output_results(citations, args.format)

    if args.direction == "both":
        time.sleep(RATE_LIMIT_DELAY)

    if args.direction in ("references", "both"):
        references = get_references(args.paper, limit=args.limit, fields=fields)
        references = filter_by_year(references, args.year)
        if args.sort_citations:
            references.sort(key=lambda p: p.get("citationCount", 0), reverse=True)
        if args.direction == "both":
            print(f"\n{'═' * 60}")
            print(f"  REFERENCED PAPERS ({len(references)})")
            print(f"{'═' * 60}")
        output_results(references, args.format)


if __name__ == "__main__":
    main()
