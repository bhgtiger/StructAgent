# Model and software versions

Status: draft. Needs reconciliation against session logs before submission.

Manuscript currently mentions:

- Anthropic Claude Opus 4.6 as primary backend for Maria and Annika;
- OpenAI ChatGPT/GPT 5.4 as Maria consultation backend;
- Qwen 2.5 7B for lightweight local summarization/logging/compaction.

P0 action: verify exact model identifiers, provider names, settings, and access dates used in each example and manuscript-writing session. Current active runtime observed during release audit was OpenAI Codex/GPT-5.5, so manuscript/backend wording must be checked carefully.


## Optional public database MCP tools

- PDBe MCP package: `pdbe-mcp-server` from `pdbeurope/pdbe-mcp-servers`.
- Recommended servers: `pdbe_api_server` and `pdbe_search_server` over `stdio`.
- No PDBe API key is required for these public API/search servers.
- The graph server is intentionally not part of the default StructAgent setup because it requires a local PDBe-KB Neo4j deployment.
