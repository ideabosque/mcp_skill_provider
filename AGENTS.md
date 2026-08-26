# Agent Notes for mcp_skill_provider

## Project Basics

- Python project managed via `pyproject.toml` (setuptools backend).
- Package name: `mcp_skill_provider`.
- No CLI entrypoint — installed as a package and loaded by `mcp_daemon_engine`.
- Dev dependencies: `pytest`, `black`, `ruff`.
- Uses `pyhumps` (not `humps`) for `decamelize` — see `pyproject.toml` comment.

## Architecture

`mcp_skill_provider` is a flat composition of mixins that expose Harness Engineering skill tools through `mcp_daemon_engine`.

```
mcp_skill_provider/
  __init__.py                # Exports MCPSkillProvider + MCP_CONFIGURATION
  mcp_skill_provider.py      # Facade class composing mixins
  mcp_configuration.py       # MCP_CONFIGURATION dict (tools + inputSchema)
  graphql_client.py          # GraphQLClient → HTTP/2 to harness_engineering_engine
  graphql_backed_processor.py # Root base: logger, setting, graphql_client
  skill_mixin.py             # search_skills, get_skill
  command_mixin.py           # run_command
  error_handler.py           # Decorators + skill-specific ErrorCode constants
```

### How it connects to mcp_daemon_engine

`mcp_daemon_engine` loads MCP modules via the `loadMcpConfiguration` GraphQL mutation. The `MCP_CONFIGURATION` dict declares:

- Module name: `mcp_skill_provider`
- Class: `mcp_skill_provider.mcp_skill_provider.MCPSkillProvider`
- Three functions: `search_skills`, `get_skill`, `run_command`

`GraphQLClient.execute_query()` posts to the module's configured `graphql_modules.harness_engineering.endpoint` with either a silvaengine_gateway JWT Bearer token (preferred) or `x-api-key` header.

### Code Style

- Follow SilvaEngine conventions: `__future__` import, `__author__ = "bibow"` header, type hints.
- All GraphQL calls go through `GraphQLClient.execute_query()` — never import `harness_engineering_engine` directly.
- Field names returned from GraphQL are camelCase; the mixins call `humps.decamelize()` to normalize to snake_case before returning to the MCP caller.
- Errors use the `error_handler` decorator pattern: `@handle_errors(operation_name="...")` on every public method, with `propagate_error_if_present()` used to forward backend errors.

### Testing

No tests exist yet. Integration testing depends on `mcp_daemon_engine` and a live `harness_engineering_engine` GraphQL endpoint.

### Security Notes

- `run_command` **never** executes commands locally; it always delegates to `harness_engineering_engine.runCommand` via GraphQL.
- The module does not accept filesystem roots, environment overrides, or execution policy changes.
- Tenant identity is inherited from `mcp_daemon_engine` gateway context, never from user input.
