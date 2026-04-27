#!/usr/bin/env python3
"""
pdf_split.py — Pure Python PDF extractor for academic papers.

Takes a PDF → outputs clean sectioned markdown + extracted figures.

Usage:
    python3 pdf_split.py input.pdf [--output-dir DIR] [--compact] [--no-refs]

Modes:
    default   Full extraction (~15k tokens for a 12-page paper)
    --compact Strip references, deduplicate, clean noise (~8-10k tokens)
    --no-refs Just drop the references section

Dependencies: PyMuPDF (fitz)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF


# ── Section detection patterns ──────────────────────────────────────────────

SECTION_PATTERNS = [
    # Numbered: "1. Introduction", "3.4.1. Dihedral restraints"
    # Must start with capital letter (not articles/prepositions) and be ≤80 chars total
    r"^(\d{1,2}(?:\.\d{1,2}){0,3})\s*[.)]\s*([A-Z][A-Za-z].{1,75})$",
    # Unnumbered common headings
    r"^(Abstract|Introduction|Background|Methods?|Materials?\s+and\s+Methods?|"
    r"Experimental|Results?|Results?\s+and\s+Discussion|Discussion|"
    r"Conclusions?(?:\s+and\s+\w[\w\s]*)?|Summary|Acknowledgm?ents?|"
    r"References?|Bibliography|"
    r"Supporting\s+Information|Supplementary|Appendix|Data\s+Availability|"
    r"Author\s+Contributions?|Competing\s+Interests?|Funding|"
    r"Declaration\s+of\s+Interests?|Ethics|Code\s+Availability)\s*$",
]

SKIP_HEADING_PATTERNS = [
    r"^\d{1,4}$",
    r"^research\s+papers?\s*$",
    r"^(ISSN|DOI|https?://)\s",
    r"^\d{4}\.\s*,?\s",
    r"^\d{4}\.\s",
    r"^Author\s+Manuscript\s*$",           # PubMed Central running header
    r"^HHS\s+Public\s+Access\s*$",         # HHS header
    r"^Author\s+manuscript\s*",            # case variants
]

# Running headers / noise to strip from body text (standalone lines)
NOISE_LINE_PATTERNS = [
    r"^research\s+papers?\s*$",
    r"^\d{1,4}$",                          # bare page numbers
    r"^ISSN\s+\d",
    r"^Acta\s+Cryst\.\s*\(\d{4}\)",       # journal running header
    r"^\w+\s+[·�]\s*\w+$",                # "Author · Title" running headers
    r"^Acta\s+Cryst\.\s+\(\d{4}\)\.\s+D\d+",
    r"^Figure\s+\d+$",                     # bare "Figure N" lines
    r"^Author\s+Manuscript\s*$",
    r"^HHS\s+Public\s+Access\s*$",
]

# Inline noise patterns to strip from within paragraph text
INLINE_NOISE_PATTERNS = [
    r"\s*\w+\s+[·�]\s*\w+\s+Acta\s+Cryst\.\s*\(\d{4}\)\.\s*D\d+,\s*\d+[–-]\d+\s*",  # "Croll · ISOLDE Acta Cryst. (2018). D74, 519–530"
    r"\s*Acta\s+Cryst\.\s*\(\d{4}\)\.\s*D\d+,\s*\d+[–-]\d+\s+\w+\s+[·�]\s*\w+\s*",  # reversed order
    r"\s*\w+\s+[·�]\w+\s*",               # "Croll ·ISOLDE" (no space after ·)
    r"\s*research\s+papers?\s*",           # inline "research papers"
]


def extract_text_blocks(doc: fitz.Document) -> list[dict]:
    """Extract text with font metadata from each page."""
    pages = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        page_data = {"page": page_num + 1, "blocks": []}

        for block in blocks:
            if block["type"] != 0:
                continue
            for line in block.get("lines", []):
                text_parts = []
                max_size = 0
                is_bold = False
                for span in line.get("spans", []):
                    text_parts.append(span["text"])
                    max_size = max(max_size, span["size"])
                    font = span.get("font", "")
                    if "bold" in font.lower() or "Bold" in font:
                        is_bold = True

                full_text = "".join(text_parts).strip()
                if full_text:
                    page_data["blocks"].append({
                        "text": full_text,
                        "font_size": round(max_size, 1),
                        "bold": is_bold,
                        "bbox": line["bbox"],
                    })

        pages.append(page_data)
    return pages


def extract_metadata(doc: fitz.Document, pages: list[dict]) -> dict:
    """Extract title, authors, DOI, journal from PDF metadata + first page heuristics."""
    meta = doc.metadata or {}
    result = {
        "title": meta.get("title", "").strip() or None,
        "authors": meta.get("author", "").strip() or None,
        "doi": None,
        "journal": None,
        "year": None,
        "keywords": None,
    }

    if not pages:
        return result

    first_page = pages[0]["blocks"]

    # ── DOI ──
    for page in pages[:2]:
        for block in page["blocks"]:
            doi_match = re.search(r"10\.\d{4,}/\S+", block["text"])
            if doi_match:
                result["doi"] = doi_match.group(0).rstrip(".,;)")
                break
        if result["doi"]:
            break

    # ── Title ── largest font on first page, multi-line join
    if first_page:
        max_size = max(b["font_size"] for b in first_page)
        title_blocks = [b for b in first_page
                        if b["font_size"] >= max_size - 0.5
                        and len(b["text"].split()) > 1]
        if title_blocks:
            # Join consecutive title-sized blocks
            title_parts = []
            for b in title_blocks:
                t = b["text"].strip()
                # Stop if we hit author/affiliation territory
                if re.match(r"^[A-Z][a-z]+\s+[A-Z][a-z]+\s*\*?$", t):
                    break
                if "@" in t or "correspondence" in t.lower():
                    break
                title_parts.append(t)
            if title_parts:
                joined = " ".join(title_parts)
                # Clean common prefixes from running headers that share title font
                joined = re.sub(r"^research\s+papers?\s+", "", joined, flags=re.IGNORECASE).strip()
                # Use this even if PDF metadata had a truncated version
                if not result["title"] or len(joined) > len(result["title"]):
                    result["title"] = joined

    # ── Authors ── look for name patterns near the title
    if not result["authors"] and first_page:
        # Find the title block index range
        max_size = max(b["font_size"] for b in first_page)
        title_end_idx = 0
        for i, b in enumerate(first_page):
            if b["font_size"] >= max_size - 0.5:
                title_end_idx = i

        # Search blocks after title for author-like text
        for b in first_page[title_end_idx + 1: title_end_idx + 6]:
            text = b["text"].strip()
            # Common author patterns: "Name Name*", "Name, Name and Name"
            # Must have at least 2 capitalized words, may have *, †, ‡
            clean = re.sub(r"[*†‡§¶\d,]", "", text).strip()
            words = clean.split()
            if 2 <= len(words) <= 20:
                cap_words = sum(1 for w in words if w[0].isupper())
                if cap_words >= 2 and cap_words >= len(words) * 0.5:
                    # Likely authors — skip if it's an institution
                    if not re.search(r"(University|Institute|Department|Laboratory|Hospital|School|College)", text, re.IGNORECASE):
                        result["authors"] = text.rstrip("*†‡§¶ ")
                        break

    # ── Year ──
    for block in first_page:
        year_match = re.search(r"\b(19|20)\d{2}\b", block["text"])
        if year_match:
            result["year"] = year_match.group(0)
            break

    # ── Keywords ──
    for page in pages[:2]:
        for block in page["blocks"]:
            kw_match = re.match(r"Keywords?:\s*(.+)", block["text"], re.IGNORECASE)
            if kw_match:
                result["keywords"] = kw_match.group(1).strip().rstrip(".")
                break

    # ── Journal ──
    journal_patterns = [
        r"(Acta Cryst\w*\.?\s*(?:Section\s+)?\w*)",
        r"(Nature\s+\w+)", r"(Science\s+\w+)",
        r"(PNAS|Proc\.\s*Natl\.?\s*Acad\.?\s*Sci\.?)",
        r"(J\.?\s*(?:Am\.?\s*)?Chem\.?\s*Soc\.?)",
        r"(eLife|Cell|Proteins?|Structure|EMBO\s+\w+)",
        r"(Bioinformatics|Nucleic\s+Acids\s+Res\.?)",
        r"(J\.?\s*Mol\.?\s*Biol\.?|J\.?\s*Struct\.?\s*Biol\.?)",
        r"(Methods\s+Enzymol\.?)",
    ]
    for block in first_page:
        for pat in journal_patterns:
            m = re.search(pat, block["text"], re.IGNORECASE)
            if m:
                result["journal"] = m.group(1).strip()
                break
        if result["journal"]:
            break

    return result


def _is_noise_line(text: str) -> bool:
    """Check if a line is a running header, page number, or other noise."""
    stripped = text.strip()
    if len(stripped) < 3:
        return True
    for pat in NOISE_LINE_PATTERNS:
        if re.match(pat, stripped, re.IGNORECASE):
            return True
    return False


def _dehyphenate(text: str) -> str:
    """Fix hyphenation at line breaks. 'pro-\ntein' → 'protein'."""
    # Pattern: word fragment ending in hyphen + word fragment starting lowercase
    return re.sub(r"(\w)- (\w)", r"\1\2", text)


def detect_sections(pages: list[dict]) -> list[dict]:
    """Detect section boundaries from text blocks."""
    sections = []
    current_section = {"title": "Header", "level": 0, "content": []}

    all_sizes = [b["font_size"] for p in pages for b in p["blocks"]]
    if not all_sizes:
        return sections

    size_counts: dict[float, int] = {}
    for s in all_sizes:
        rounded = round(s, 0)
        size_counts[rounded] = size_counts.get(rounded, 0) + 1
    body_size = max(size_counts, key=size_counts.get)

    in_references = False  # Track if we're past the References heading

    for page in pages:
        for block in page["blocks"]:
            text = block["text"]
            font_size = block["font_size"]
            is_bold = block["bold"]

            is_heading = False
            heading_text = text
            heading_level = 1

            skip = False
            for sp in SKIP_HEADING_PATTERNS:
                if re.match(sp, text.strip(), re.IGNORECASE):
                    skip = True
                    break

            if not skip:
                for i, pattern in enumerate(SECTION_PATTERNS):
                    m = re.match(pattern, text.strip(), re.IGNORECASE)
                    if m:
                        if i == 0:  # numbered section
                            num = m.group(1)
                            if re.match(r"^(19|20)\d{2}$", num):
                                break
                            # Don't treat numbered lines as sections if inside references
                            if in_references:
                                break
                            heading_text = f"{num}. {m.group(2)}"
                            heading_level = num.count(".") + 1
                        else:
                            heading_text = m.group(0).strip()
                            heading_level = 1
                            # Track entering references
                            if re.match(r"^(References?|Bibliography)\s*$", heading_text, re.IGNORECASE):
                                in_references = True
                        is_heading = True
                        break

                if not is_heading and font_size > body_size + 1.5:
                    words = text.split()
                    if 2 <= len(words) <= 15 and text[0].isupper():
                        is_heading = True
                        heading_text = text
                        heading_level = 1 if font_size > body_size + 3 else 2
                        if re.match(r"^(References?|Bibliography)\s*$", heading_text, re.IGNORECASE):
                            in_references = True
                elif not is_heading and is_bold and font_size >= body_size:
                    words = text.split()
                    if 2 <= len(words) <= 12 and text[0].isupper():
                        numbered = re.match(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\s*[.)]\s*(.+)$", text)
                        if numbered and not re.match(r"^(19|20)\d{2}$", numbered.group(1)):
                            if not in_references:
                                is_heading = True
                                heading_text = text
                                heading_level = numbered.group(1).count(".") + 1

            if is_heading:
                if current_section["content"] or current_section["title"] != "Header":
                    sections.append(current_section)
                current_section = {
                    "title": heading_text,
                    "level": heading_level,
                    "content": [],
                    "page": page["page"],
                }
            else:
                current_section["content"].append({
                    "text": text,
                    "page": page["page"],
                })

    if current_section["content"]:
        sections.append(current_section)

    return sections


def extract_figures(doc: fitz.Document, output_dir: Path) -> list[dict]:
    """Extract images from PDF and save to disk."""
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(exist_ok=True)

    figures = []
    seen_xrefs = set()

    for page_num, page in enumerate(doc):
        images = page.get_images(full=True)
        for img_idx, img in enumerate(images):
            xref = img[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                base_image = doc.extract_image(xref)
                if not base_image:
                    continue

                img_bytes = base_image["image"]
                img_ext = base_image.get("ext", "png")
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                if width < 50 or height < 50:
                    continue

                filename = f"fig_p{page_num+1}_{img_idx+1}.{img_ext}"
                filepath = figures_dir / filename
                with open(filepath, "wb") as f:
                    f.write(img_bytes)

                figures.append({
                    "file": str(filepath),
                    "page": page_num + 1,
                    "width": width,
                    "height": height,
                    "size_kb": len(img_bytes) // 1024,
                })
            except Exception as e:
                print(f"  Warning: couldn't extract image xref={xref}: {e}", file=sys.stderr)

    return figures


# ── Compact mode: sections to drop or truncate ─────────────────────────────

# Sections to drop entirely in compact mode
COMPACT_DROP_SECTIONS = {
    "references", "bibliography", "acknowledgements", "acknowledgments",
    "funding", "author contributions", "competing interests",
    "declaration of interests", "supporting information", "supplementary",
}

# Sections where content is less critical — keep heading + first paragraph only
COMPACT_TRUNCATE_SECTIONS = {
    "header",
}


def _section_title_lower(title: str) -> str:
    """Normalize section title for matching."""
    # Strip leading numbers: "6. Conclusions and future directions" → "conclusions and future directions"
    return re.sub(r"^\d+(?:\.\d+)*\.\s*", "", title).strip().lower()


def sections_to_markdown(metadata: dict, sections: list[dict], figures: list[dict],
                          compact: bool = False, no_refs: bool = False) -> str:
    """Convert extracted sections to clean markdown."""
    lines = []

    # Metadata block
    lines.append(f"# {metadata.get('title') or 'Untitled'}")
    lines.append("")
    lines.append("## Metadata")
    if metadata.get("authors"):
        lines.append(f"- **Authors:** {metadata['authors']}")
    if metadata.get("journal"):
        lines.append(f"- **Journal:** {metadata['journal']}")
    if metadata.get("year"):
        lines.append(f"- **Year:** {metadata['year']}")
    if metadata.get("doi"):
        lines.append(f"- **DOI:** https://doi.org/{metadata['doi']}")
    if metadata.get("keywords"):
        lines.append(f"- **Keywords:** {metadata['keywords']}")
    lines.append("")

    for section in sections:
        level = section.get("level", 1)
        title = section["title"]
        title_lower = _section_title_lower(title)

        # Skip empty header sections
        if title == "Header" and not section["content"]:
            continue

        # Compact: drop certain sections entirely
        if compact and title_lower in COMPACT_DROP_SECTIONS:
            continue
        if no_refs and title_lower in {"references", "bibliography"}:
            continue

        hashes = "#" * min(level + 1, 4)
        lines.append(f"{hashes} {title}")
        lines.append("")

        # Build paragraphs from content blocks
        content_blocks = section["content"]

        # Compact: truncate header section
        if compact and title_lower in COMPACT_TRUNCATE_SECTIONS:
            content_blocks = content_blocks[:3]

        paragraphs = []
        current_para = []

        for block in content_blocks:
            text = block["text"]

            # Filter noise lines
            if _is_noise_line(text):
                continue

            # Paragraph break detection
            if current_para and (
                text[0].isupper() and
                current_para[-1].rstrip().endswith(".")
            ):
                paragraphs.append(" ".join(current_para))
                current_para = []

            # De-hyphenation at line breaks
            if current_para and current_para[-1].endswith("-"):
                # Check if it's a real hyphen (e.g., "well-known") or a line-break artifact
                last = current_para[-1]
                # If lowercase letter before hyphen and lowercase after → likely line-break
                if last[-2:] != "--" and text[0].islower():
                    current_para[-1] = last[:-1]  # remove hyphen, words will join with space removed below
                current_para.append(text)
            else:
                current_para.append(text)

        if current_para:
            paragraphs.append(" ".join(current_para))

        for para in paragraphs:
            para = re.sub(r"\s+", " ", para).strip()
            # Strip inline running headers
            for ipat in INLINE_NOISE_PATTERNS:
                para = re.sub(ipat, " ", para)
            # Final de-hyphenation pass for joined fragments
            para = _dehyphenate(para)
            para = re.sub(r"\s+", " ", para).strip()
            if para:
                lines.append(para)
                lines.append("")

    # Figures summary
    if figures:
        lines.append("## Extracted Figures")
        lines.append("")
        for fig in figures:
            lines.append(f"- `{os.path.basename(fig['file'])}` — page {fig['page']}, "
                         f"{fig['width']}×{fig['height']} px, {fig['size_kb']} KB")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Extract academic paper PDF to structured markdown")
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument("--output-dir", "-o", help="Output directory (default: same as PDF)")
    parser.add_argument("--no-figures", action="store_true", help="Skip figure extraction")
    parser.add_argument("--no-refs", action="store_true", help="Drop references section")
    parser.add_argument("--compact", action="store_true",
                        help="Compact mode: drop refs, acknowledgments, truncate noise → saves ~40%% tokens")
    parser.add_argument("--json", action="store_true", help="Also output JSON structure")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: {pdf_path} not found", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else pdf_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing: {pdf_path.name}")
    doc = fitz.open(str(pdf_path))
    print(f"  Pages: {len(doc)}")

    print("  Extracting text blocks...")
    pages = extract_text_blocks(doc)

    print("  Parsing metadata...")
    metadata = extract_metadata(doc, pages)
    print(f"  Title: {metadata.get('title', '?')[:80]}")
    print(f"  Authors: {metadata.get('authors', 'not found')}")
    print(f"  DOI: {metadata.get('doi', 'not found')}")

    print("  Detecting sections...")
    sections = detect_sections(pages)
    print(f"  Found {len(sections)} sections")
    for s in sections:
        indent = "  " * s.get("level", 1)
        n_blocks = len(s["content"])
        print(f"    {indent}{s['title']} ({n_blocks} blocks)")

    figures = []
    if not args.no_figures:
        print("  Extracting figures...")
        figures = extract_figures(doc, output_dir)
        print(f"  Found {len(figures)} figures")

    stem = pdf_path.stem
    compact = args.compact
    no_refs = args.no_refs or args.compact

    # Full markdown
    md_content = sections_to_markdown(metadata, sections, figures,
                                       compact=compact, no_refs=no_refs)
    suffix = "_compact" if compact else "_extracted"
    md_path = output_dir / f"{stem}{suffix}.md"
    with open(md_path, "w") as f:
        f.write(md_content)
    print(f"  Markdown: {md_path} ({len(md_content)} chars)")

    # JSON (optional)
    if args.json:
        json_data = {
            "metadata": metadata,
            "sections": [
                {
                    "title": s["title"],
                    "level": s.get("level", 1),
                    "page": s.get("page"),
                    "content": " ".join(b["text"] for b in s["content"]),
                }
                for s in sections
            ],
            "figures": figures,
        }
        json_path = output_dir / f"{stem}_structure.json"
        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=2)
        print(f"  JSON: {json_path}")

    doc.close()
    print("Done.")


if __name__ == "__main__":
    main()
