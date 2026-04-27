#!/usr/bin/env python3
"""Get paper recommendations from Semantic Scholar.

Usage:
    # Single-paper recommendations
    python s2_recommend.py 649def34f8be52c8b66281af98ae884c09aef38b --limit 10

    # Multi-paper recommendations (positive seeds)
    python s2_recommend.py paper_id_1 paper_id_2 paper_id_3 --limit 15

    # With negative examples (papers to avoid similarity to)
    python s2_recommend.py paper_id_1 --negative bad_id_1 bad_id_2

    # From DOI
    python s2_recommend.py DOI:10.1038/s41586-021-03819-2 --limit 10
"""

import argparse
import sys

from s2_common import (
    API_BASE, REC_BASE, STANDARD_FIELDS, COMPACT_FIELDS,
    s2_get, s2_post, output_results,
)


def recommend_single(paper_id: str, limit: int = 10, full: bool = False) -> list[dict]:
    """Get recommendations based on a single paper."""
    fields = STANDARD_FIELDS if full else COMPACT_FIELDS
    url = f"{REC_BASE}/papers/forpaper/{paper_id}"
    params = {"fields": fields, "limit": str(limit)}
    data = s2_get(url, params)
    if data:
        return data.get("recommendedPapers", [])
    return []


def recommend_multi(positive_ids: list[str], negative_ids: list[str] = None,
                    limit: int = 10, full: bool = False) -> list[dict]:
    """Get recommendations based on multiple papers (positive + optional negative seeds)."""
    fields = STANDARD_FIELDS if full else COMPACT_FIELDS
    url = f"{REC_BASE}/papers/"
    params = {"fields": fields, "limit": str(limit)}
    body = {"positivePaperIds": positive_ids}
    if negative_ids:
        body["negativePaperIds"] = negative_ids
    data = s2_post(url, body, params)
    if data:
        return data.get("recommendedPapers", [])
    return []


def main():
    parser = argparse.ArgumentParser(description="Semantic Scholar paper recommendations")
    parser.add_argument("papers", nargs="+",
                        help="Seed paper ID(s). Use DOI:xxx format for DOIs.")
    parser.add_argument("--negative", nargs="*", default=[],
                        help="Negative seed paper IDs (papers to avoid)")
    parser.add_argument("--limit", type=int, default=10, help="Max recommendations (default: 10)")
    parser.add_argument("--full", action="store_true", help="Include abstracts")
    parser.add_argument("--format", choices=["pretty", "json", "tsv"], default="pretty",
                        help="Output format (default: pretty)")
    args = parser.parse_args()

    if len(args.papers) == 1 and not args.negative:
        # Single-paper recommendations
        papers = recommend_single(args.papers[0], limit=args.limit, full=args.full)
    else:
        # Multi-paper recommendations
        papers = recommend_multi(args.papers, args.negative, limit=args.limit, full=args.full)

    if not papers:
        print("No recommendations found.", file=sys.stderr)
        sys.exit(1)

    output_results(papers, args.format)


if __name__ == "__main__":
    main()
