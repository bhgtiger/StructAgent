# PDBe MCP setup for StructAgent-style agents

StructAgent can optionally expose public PDBe tools to the Maria/Annika agent pair through the upstream [`pdbeurope/pdbe-mcp-servers`](https://github.com/pdbeurope/pdbe-mcp-servers) package.

This integration is optional. It is useful when agents need to query public PDB/PDBe metadata, entry annotations, assemblies, ligands, validation summaries, or the PDBe search index during literature review, model interpretation, or structural-biology planning.

## Recommended servers

Enable the two public, keyless servers:

- `pdbe-api` — PDBe API tools.
- `pdbe-search` — PDBe search schema/query tools.

Do **not** enable `pdbe_graph_server` unless you deliberately maintain a local PDBe-KB Neo4j graph instance.

## OpenClaw-style MCP config example

```json
{
  "mcp": {
    "servers": {
      "pdbe-api": {
        "command": "uvx",
        "args": [
          "pdbe-mcp-server",
          "--server-type",
          "pdbe_api_server",
          "--transport",
          "stdio"
        ],
        "codex": {
          "agents": ["maria", "gemini"]
        }
      },
      "pdbe-search": {
        "command": "uvx",
        "args": [
          "pdbe-mcp-server",
          "--server-type",
          "pdbe_search_server",
          "--transport",
          "stdio"
        ],
        "codex": {
          "agents": ["maria", "gemini"]
        }
      }
    }
  }
}
```

Notes:

- `--transport stdio` is required for stdio MCP projection in this setup.
- Scope the servers to the agents that need them rather than projecting them globally. In the StructAgent deployment pattern, that is Maria plus Annika/Gemini.
- No PDBe API key is required for the API or search servers.
- For reproducible releases, pin the package version according to your host runtime's MCP/package-management conventions.

## Verification

After restarting or refreshing the agent runtime, verify both servers are visible to the target agents. If MCP tool discovery lags in an existing session, start a fresh agent session before concluding the setup failed.

Fallback behavior: if MCP tools are unavailable, agents can still use public PDBe REST/search endpoints through normal web/API access, but they should report that the dedicated MCP tools were not available.
