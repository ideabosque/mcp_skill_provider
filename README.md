# mcp_skill_provider

MCP skill provider — search, retrieve, and execute commands for Harness Engineering skills.

`mcp_skill_provider` is a standalone MCP module registered with [`mcp_daemon_engine`](../mcp_daemon_engine/). It exposes three tools to agents:

- `search_skills(query, limit?)` — lexical search over the skill catalog
- `get_skill(name)` — retrieve full skill instructions from Harness Engineering
- `run_command(name, argv, workspace_scope?)` — execute an allowlisted command for a skill

## Installation

```bash
pip install -e .
```

## Configuration

Set the Harness Engineering GraphQL endpoint via environment variable:

```bash
HSK_GRAPHQL_ENDPOINT=http://localhost:8000/graphql
```

## Usage with mcp_daemon_engine

Register the module through `mcp_daemon_engine`'s `loadMcpConfiguration` mutation. `mcp_configuration.py` already declares the `tools`, `modules`, and `module_links` blocks the daemon needs — it points every tool at:

```json
{
  "module_name": "mcp_skill_provider",
  "class_name": "mcp_skill_provider.mcp_skill_provider.MCPSkillProvider",
  "package_name": "mcp_skill_provider",
  "source": ""
}
```

`source: ""` means the package must be importable from the daemon's `sys.path` (e.g. `pip install -e .`); it is not fetched from S3. Real GraphQL endpoint/credential values are supplied at registration time via `loadMcpConfiguration`'s `variables` argument, which overrides the placeholder `setting.graphql_modules` values in the manifest.

## License

MIT
