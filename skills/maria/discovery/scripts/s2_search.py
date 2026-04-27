#!/usr/bin/env python3
"""Search Semantic Scholar for papers by keyword.

Usage:
    python s2_search.py "cryo-EM model building" --year 2020- --limit 20
    python s2_search.py "MDFF flexible fitting" --venue "Nature Methods" --min-citations 10
    python s2_search.py "AlphaFold" --type JournalArticle --year 2021-2023 --format json
    python s2_search.py --doi 10.1038/s41586-021-03819-2
    python s2_search.py --id 649def34f8be52c8b66281af98ae884c09aef38b
"""

import argparse
import sys
import time

from s2_common import (
    API_BASE, COMPACT_FIELDS, STANDARD_FIELDS, RATE_LIMIT_DELAY,
    s2_get, output_results,
)


def search_bulk(query: str, year: str = None, venue: str = None,
                pub_types: str = None, min_citations: int = None,
                open_access: bool = False, fields_of_study: str = None,
                limit: int = 20, sort: str = None,
                full: bool = False) -> list[dict]:
    """Bulk search using the paper/search/bulk endpoint."""
    url = f"{API_BASE}/paper/search/bulk"
    fields = STANDARD_FIELDS if full else COMPACT_FIELDS
    params = {"query": query, "fields": fields}
    if year:
        params["year"] = year
    if venue:
        params["venue"] = venue
    if pub_types:
        params["publicationTypes"] = pub_types
    if min_citations is not None:
        params["minCitationCount"] = str(min_citations)
    if open_access:
        params["openAccessPdf"] = ""
    if fields_of_study:
        params["fieldsOfStudy"] = fields_of_study
    if sort:
        params["sort"] = sort

    all_papers = []
    token = None

    while len(all_papers) < limit:
        if token:
            params["token"] = token
        data = s2_get(url, params)
        if not data:
            break
        papers = data.get("data", [])
        if not papers:
            break
        all_papers.extend(papers)
        token = data.get("token")
        if not token:
            break
        time.sleep(RATE_LIMIT_DELAY)

    return all_papers[:limit]


def lookup_paper(paper_id: str) -> dict | None:
    """Look up a single paper by S2 ID, DOI, or other external ID."""
    url = f"{API_BASE}/paper/{paper_id}"
    return s2_get(url, {"fields": STANDARD_FIELDS})


def batch_lookup(paper_ids: list[str]) -> list[dict]:
    """Batch lookup multiple papers (up to 500)."""
    url = f"{API_BASE}/paper/batch"
    params = {"fields": STANDARD_FIELDS}
    data = []
    # API limit is 500 per batch
    for i in range(0, len(paper_ids), 500):
        chunk = paper_ids[i:i + 500]
        body = {"ids": chunk}
        from s2_common import s2_post
        resp = s2_post(url, body, params)
        if resp:
            data.extend([p for p in resp if p])
        time.sleep(RATE_LIMIT_DELAY)
    return data


def main():
    parser = argparse.ArgumentParser(description="Search Semantic Scholar")
    parser.add_argument("query", nargs="?", help="Search query (keywords)")
    parser.add_argument("--doi", help="Look up paper by DOI")
    parser.add_argument("--id", help="Look up paper by S2 paper ID")
    parser.add_argument("--ids", nargs="+", help="Batch lookup by multiple S2 IDs")
    parser.add_argument("--year", help="Year filter: '2020-', '2020-2023', '2023'")
    parser.add_argument("--venue", help="Venue filter (e.g., 'Nature Methods')")
    parser.add_argument("--type", dest="pub_type",
                        help="Publication type: JournalArticle, Conference, Review, etc.")
    parser.add_argument("--min-citations", type=int, help="Minimum citation count")
    parser.add_argument("--open-access", action="store_true", help="Only papers with open access PDF")
    parser.add_argument("--field", help="Field of study filter (e.g., 'Biology')")
    parser.add_argument("--sort", help="Sort: citationCount:desc, publicationDate:desc, etc.")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    parser.add_argument("--full", action="store_true", help="Include abstracts in results")
    parser.add_argument("--format", choices=["pretty", "json", "tsv"], default="pretty",
                        help="Output format (default: pretty)")
    args = parser.parse_args()

    # Single paper lookup modes
    if args.doi:
        paper = lookup_paper(f"DOI:{args.doi}")
        if paper:
            output_results([paper], args.format)
        else:
            print("Paper not found.", file=sys.stderr)
            sys.exit(1)
        return

    if args.id:
        paper = lookup_paper(args.id)
        if paper:
            output_results([paper], args.format)
        else:
            print("Paper not found.", file=sys.stderr)
            sys.exit(1)
        return

    if args.ids:
        papers = batch_lookup(args.ids)
        output_results(papers, args.format)
        return

    # Search mode
    if not args.query:
        parser.error("Provide a search query or use --doi/--id for lookup")

    papers = search_bulk(
        query=args.query,
        year=args.year,
        venue=args.venue,
        pub_types=args.pub_type,
        min_citations=args.min_citations,
        open_access=args.open_access,
        fields_of_study=args.field,
        limit=args.limit,
        sort=args.sort,
        full=args.full,
    )

    if not papers:
        print("No results found.", file=sys.stderr)
        sys.exit(1)

    output_results(papers, args.format)


if __name__ == "__main__":
    main()
