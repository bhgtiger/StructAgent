---
name: database
description: Query, search, cross-reference, and answer questions from the project paper databases. Use when asked to find papers, check what's in the database, explore connections, identify gaps, compare papers, or answer literature questions. NOT for filing papers (that's part of paper-reader and review-paper skills).
---

# Database — Query & Cross-Reference

The database skill is for **using** the collected literature, not for filing into it. Filing is handled by the paper-reader and review-paper skills.

## When to Use

- "What papers do we have on validation?"
- "Show me the connection graph around ISOLDE"
- "What's missing in our coverage of map sharpening?"
- "Compare what X and Y say about refinement"
- "How many papers per cluster?"
- "Find all papers that mention ChimeraX"

## Database Structure

Each project can have one or more YAML database files:

```
database/
├── database_<collection>.yaml    # One or more collections
├── digests/                       # Individual paper digests (read these for deep answers)
├── extractions/                   # Raw extracted text from PDFs
├── papers_incoming/               # Archived source PDFs
└── connections.md                 # Optional human-written cross-reference notes
```

### YAML Schema Quick Reference

```yaml
papers:
  - id: 1                          # Unique integer (may have gaps)
    key: author_year_short          # Unique snake_case identifier
    title: "Full title"
    authors: ["Author One", ...]
    year: 2024
    journal: "Journal Name"
    doi: "10.xxxx/xxxxx"
    paper_type: method              # method | empirical | review | benchmark | computational | theoretical | workshop_talk
    significance: high              # high | medium | low
    tags: ["keyword1", "keyword2"]
    digest: "digests/YYYY-MM-DD_author_short.md"
    pdf: "papers_incoming/author_year.pdf"
    maria_opinion: "Brief assessment"
    connections: ["other_key_1", "other_key_2"]   # Always use exact key strings
```

## Query Patterns

### 1. Search by Keywords/Tags

```python
# Find papers matching tags or title keywords
for p in db['papers']:
    if any('validation' in t.lower() for t in p.get('tags', [])):
        print(p['key'], p['title'])
```

### 2. Connection Graph Traversal

```python
# Find all papers connected to a given key (1-hop)
target = 'croll_2018_isolde_physically_realistic_environment'
connected = [p for p in db['papers'] if target in p.get('connections', [])]

# Bidirectional: also find what target connects to
target_paper = next(p for p in db['papers'] if p['key'] == target)
outgoing = target_paper.get('connections', [])
```

### 3. Gap Analysis

```python
# Find papers with no connections (orphans)
orphans = [p for p in db['papers'] if not p.get('connections')]

# Find papers with no digest
no_digest = [p for p in db['papers'] if not p.get('digest')]

# Coverage by year
from collections import Counter
years = Counter(p['year'] for p in db['papers'])
```

### 4. Deep Answer (Read Digest)

When a question needs more than metadata (e.g. "what did Gore 2017 say about ligand validation?"):
1. Find the paper in the YAML
2. Read the digest file at the path in `digest` field
3. Answer from the digest content

### 5. Cross-Database Queries

When multiple collections exist, load all YAML files and merge the paper lists. Connection keys can reference papers across collections.

## Integrity Checks

Run periodically or after batch operations:

```python
# Verify all connection keys resolve
all_keys = {p['key'] for p in all_papers}
for p in all_papers:
    for c in p.get('connections', []):
        if c not in all_keys:
            print(f"BAD: {p['key']} → {c}")

# Check for duplicate keys
from collections import Counter
dupes = [k for k, v in Counter(p['key'] for p in all_papers).items() if v > 1]

# Check for duplicate IDs
id_dupes = [k for k, v in Counter(p['id'] for p in all_papers).items() if v > 1]
```

## Principles

- **Answer from digests, not just metadata.** Tag/title search narrows candidates; digest content answers questions.
- **Connection graph is the knowledge structure.** Traversals reveal clusters, gaps, and dependencies.
- **Cross-database is first-class.** Don't assume one YAML file = one query scope.
- **Be honest about coverage.** If the database doesn't have a paper or topic, say so — don't hallucinate entries.
- **Maintenance is a query too.** Gap analysis, orphan detection, and integrity checks are legitimate database operations.
