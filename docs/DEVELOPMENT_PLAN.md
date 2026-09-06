# MCP Skill Provider — Development Plan

> **Location:** `C:\Users\bibo7\gitrepo\silvaengine\mcp_skill_provider`
> **Date:** 2026-09-06
> **Status:** v0.0.1 package scaffold complete; runtime registration with `mcp_daemon_engine` wired (P1.5 done) — integration testing (P2) not yet started; reviewed against harness_engineering_engine P8/P9 changes (2026-09-06)

---

## Overview

`mcp_skill_provider` is the MCP-facing module that gives agents access to Harness Engineering skills. It sits inside `mcp_daemon_engine` as a registered module and exposes three tools:

| Tool | Description |
|---|---|
| `search_skills(query, limit?)` | Lexical search over enabled skills by name and description |
| `get_skill(name)` | Retrieve full skill instructions and metadata — returns `body` (SKILL.md), `allowed_commands`, `cli_packages`, `references`, and triggers on-demand git refresh when the local cache is stale or missing |
| `run_command(name, argv, workspace_scope?)` | Execute an allowlisted command under the guarded command executor |

The provider holds no skill data of its own — it delegates all reads and writes to `harness_engineering_engine` via GraphQL.

---

## Known Gaps

Verified against the sibling `mcp_daemon_engine` and `harness_engineering_engine` repos on 2026-08-25; updated 2026-09-06 to reflect `harness_engineering_engine` P8 (recursive skill discovery + CLI package auto-install) and P9 (reference files + LLM-assisted section generation):

1. ~~`MCP_CONFIGURATION` has no `modules` / `module_links` entries.~~ **Fixed (P1.5).** `mcp_daemon_engine.handlers.mcp_utility.execute_tool_function` resolves a tool call to a class instance by looking up `config["module_links"]` (maps a tool `name` → `module_name`/`class_name`/`function_name`) and `config["modules"]` (maps `module_name`/`class_name` → `package_name`, `source`, `setting`). `mcp_configuration.py` now declares both blocks, pointing all three tools at `mcp_skill_provider.mcp_skill_provider.MCPSkillProvider` with `package_name="mcp_skill_provider"`, `source=""`. Verified by running `mcp_daemon_engine.handlers.mcp_handlers.validate_manifest()` directly against the manifest — passes. Real GraphQL endpoint/credential values are supplied at registration time via `loadMcpConfiguration`'s `variables` argument, which overrides the placeholder `setting.graphql_modules` values declared here.
2. **`HSK_GRAPHQL_ENDPOINT` is documented but not implemented.** `graphql_client.py` never reads environment variables — `GraphQLClient`/`GraphQLModule` are configured entirely from the `setting` dict passed into the constructor. Standalone/local testing today means constructing `MCPSkillProvider` with an explicit `graphql_modules.harness_engineering.endpoint`, not setting an env var. Either implement the env var fallback or drop the row from Configuration/README so the docs don't promise a knob that doesn't exist.
3. **`endpoint_id` / `part_id` are not `setting` keys.** At runtime, `mcp_daemon_engine` sets these on the tool instance *after* construction, by splitting the caller's `partition_key` on `#` (see `execute_tool_function`) — they are never part of the `setting` kwargs dict. `connection_id` isn't read anywhere in this codebase at all. The Configuration example below has been corrected to match.
4. **(Blocker) No `runCommand` timeout budget — 60s GraphQL ceiling races with git-refresh + command.** `graphql_client.py::GraphQLClient.execute_query` uses `httpx.Timeout(60.0, connect=15.0)` for all operations, including `runCommand`. The `runCommand` mutation first calls `skill()` on the backend, which triggers a git clone on a cache miss. If the git remote is slow, the skill load alone can consume most of the 60s budget, causing `run_command` to fail at the HTTP layer before the command starts. The error surfaces as a generic GraphQL timeout, not a "still loading skill" message. **Plan:** Add a per-operation configurable timeout (e.g. `graphql_modules.harness_engineering.command_timeout_seconds`, default 120s) for `runCommand` mutations, and surface the backend's phase (skill-load vs command-exec) in error responses so the caller can distinguish a slow refresh from a slow command.
5. **(Should fix) `get_skill` tool description doesn't guide the LLM to use `allowed_commands`.** The `get_skill` tool description in `mcp_configuration.py` says *"Retrieve full instructions and metadata for a skill"* — it doesn't mention that the returned `allowed_commands` list is the execution contract for `run_command`. An LLM that doesn't realize it must match its `run_command` argv against the returned `allowed_commands` entries will attempt unallowlisted commands and get `COMMAND_DENIED`. **Plan:** Update the `get_skill` tool description to explicitly state: *"Read the returned `body` for instructions, then call `run_command` with an `argv` that matches one of the `allowed_commands` entries."*
6. **(Should fix) No tests exist.** `mcp_skill_provider` has no test directory. Every other project in the chain has tests (`harness_engineering_engine`: 135 tests as of P9, `mcp_http_client`: has tests, `openai_completions_agent_handler`: deterministic unit tests). Any refactoring of the GraphQL contract, error handling, or the three tool methods goes unverified. **Plan:** Add unit tests for the three mixin methods (mocked `GraphQLClient`), error handler decorator, and `MCP_CONFIGURATION` manifest validation. Add integration tests for the `search_skills → get_skill → run_command` happy path once the `mcp_daemon_engine` integration test harness (P2) is in place.
7. **(Should fix) `mcp_http_client` has no request timeout.** `MCPHttpClient._send_request` creates an `aiohttp.ClientSession` with no timeout configured. If `run_command` triggers a slow backend git-refresh, the `mcp_http_client` → `mcp_daemon_engine` call hangs indefinitely. This is tracked in `mcp_http_client` (see `mcp_http_client/docs/DEVELOPMENT_PLAN.md` G-1), not here, but it affects this provider's reliability. **Plan:** Add a configurable `timeout` to `MCPHttpClient` (default 90s) so the client fails fast rather than hanging when the backend is slow.
8. **(Should fix) `get_skill` response shape changed in P9 — `cli_packages` and `references` now returned.** `harness_engineering_engine` P9 added `cli_packages` and `references` fields to the `skill(name)` response. The `mcp_skill_provider` `get_skill` tool passes these through via `humps.decamelize()` but the `inputSchema` in `mcp_configuration.py` still describes `get_skill` as *"Retrieve full instructions and metadata for a skill"* without mentioning `allowed_commands`, `cli_packages`, or `references`. An LLM calling `get_skill` doesn't know the response contains `allowed_commands` (the execution contract for `run_command`) or `references` (file contents the skill needs). **Plan:** Update the `get_skill` tool description to: *"Retrieve full instructions and metadata for a skill. Read the returned `body` for instructions, then call `run_command` with an `argv` that matches one of the `allowed_commands` entries. The response also includes `cli_packages` (declared dependencies) and `references` (file contents the skill references)."* (Overlaps with gap 5 — merged fix.)
9. **(Should fix) `searchSkills` ranking is naive — affects `search_skills` quality.** `harness_engineering_engine`'s `resolve_search_skills` (§18 G-3 in its development plan) uses lexical exact/prefix/substring matching, capped at 1000 enabled skills. This provider surfaces that search directly as the `search_skills` MCP tool — if the LLM can't find the right skill, nothing downstream runs. **Plan:** Tracked in `harness_engineering_engine/docs/DEVELOPMENT_PLAN.md` §18 G-3 (add rapidfuzz-based fuzzy ranking). This provider needs no code change, but the P2 integration tests should verify that `search_skills` returns relevant results for common query variations.
10. **(Should fix) `run_command` can't handle long-running scripts — 30s hard timeout.** `harness_engineering_engine`'s `command_executor.execute_command` (§18 G-1 in its development plan) uses `subprocess.run(..., timeout=30)` — a hard synchronous kill with no async/poll path. Any skill script that takes more than ~30s silently fails. The `run_command` MCP tool description in `mcp_configuration.py` doesn't mention the timeout or that long-running commands aren't supported. **Plan:** Tracked in `harness_engineering_engine/docs/DEVELOPMENT_PLAN.md` §18 G-1 (add `background_mode` + `pollCommand`). Once the backend supports it, this provider needs a corresponding `poll_command` tool and an updated `run_command` description.
11. **(Should fix) `run_command` output truncation doesn't indicate volume dropped.** `harness_engineering_engine`'s `command_executor` truncates stdout/stderr at 20KB and sets `truncated=true` (§18 G-4 in its development plan). The `run_command` tool description doesn't mention this cap, and the GraphQL `RunCommand` type doesn't expose how much was dropped. **Plan:** Tracked in `harness_engineering_engine/docs/DEVELOPMENT_PLAN.md` §18 G-4 (add `output_truncated_bytes`). This provider passes the result through as-is — no code change needed once the backend exposes the field.

---

## Architecture

```
Agent
  │
  ▼
mcp_daemon_engine (MCP JSON-RPC endpoint)
  │
  ▼
MCPSkillProvider                      # mcp_skill_provider.mcp_skill_provider
  │── SkillMixin.search_skills()
  │── SkillMixin.get_skill()
  └── CommandMixin.run_command()
        │
        ▼
GraphQLBackedProcessor
  │── self.graphql_client (GraphQLClient)
  │
  ▼
GraphQLClient.execute_query()
  │── HTTP/2 POST to graphql_modules.harness_engineering.endpoint
  │── Auth: silvaengine_gateway JWT Bearer or x-api-key
  │
  ▼
harness_engineering_engine
  GraphQL endpoint → services → DynamoDB / PostgreSQL / local skill cache
  │── skill(name): returns body, allowed_commands, cli_packages, references
  │── searchSkills: lexical ranked search over enabled skills
  │── runCommand: guarded execution (allowlist match, no shell, timeout, output cap)
  │── skill source: git only (no S3, no ZIP) — on-demand git refresh on cache miss
```

### Mixin composition

The `MCPSkillProvider` facade class composes two mixins, both of which extend only `GraphQLBackedProcessor`:

- **`SkillMixin`** — `search_skills(query, limit?)`, `get_skill(name)`
- **`CommandMixin`** — `run_command(name, argv, workspace_scope?)`

Each mixin's `__init__` is inherited from `GraphQLBackedProcessor`, which constructs a `GraphQLClient` and provides `self.logger`, `self.setting`, `self.graphql_client`, and the shared `_execute_graphql_query()` method.

---

## Project Layout

```
mcp_skill_provider/
├── pyproject.toml                      # setuptools, pyhumps>=3.8, httpx[http2], SilvaEngine-Utility
├── README.md
├── LICENSE
├── AGENTS.md                           # Agent-facing architecture notes (mirrors this plan)
├── docs/
│   └── DEVELOPMENT_PLAN.md             # This file
├── mcp_skill_provider/
│   ├── __init__.py                     # Exports MCPSkillProvider + MCP_CONFIGURATION
│   ├── mcp_skill_provider.py           # Facade class composing mixins
│   ├── mcp_configuration.py            # MCP_CONFIGURATION dict
│   ├── graphql_client.py               # GraphQLClient → HTTP/2, JWT auth
│   ├── graphql_backed_processor.py     # Root base for all mixins
│   ├── skill_mixin.py                  # search_skills, get_skill
│   ├── command_mixin.py                # run_command
│   └── error_handler.py                # Decorators + ErrorCode constants
└── .gitignore
```

### File responsibilities

| File | Responsibility |
|---|---|
| `mcp_configuration.py` | `MCP_CONFIGURATION` dict — declares tools and inputSchema to `mcp_daemon_engine` |
| `mcp_skill_provider.py` | Facade class `MCPSkillProvider` — flat mixin composition |
| `graphql_client.py` | `GraphQLClient` — HTTP/2 transport, JWT/x-api-key auth, retry on 401 |
| `graphql_backed_processor.py` | `GraphQLBackedProcessor` — shared `logger`, `setting`, `graphql_client` |
| `skill_mixin.py` | `SkillMixin` — `search_skills`, `get_skill` |
| `command_mixin.py` | `CommandMixin` — `run_command` |
| `error_handler.py` | `@handle_errors` decorator, `ErrorCode` constants, validation utilities |

---

## Configuration

`mcp_skill_provider` settings follow the same pattern as `mcp_hospirfq_processor`. The module receives its settings via `setting` dict at instantiation (provided by `mcp_daemon_engine` from the gateway or local config).

### Example `setting` dict (provided by mcp_daemon_engine)

```python
{
    "graphql_modules": {
        "harness_engineering": {
            "class_name": "harness_engineering_engine.main.HarnessEngineeringEngine",
            "endpoint": "https://{endpoint_id}.execute-api.us-east-1.amazonaws.com/dev/graphql",
            "x_api_key": "...",
            "gateway_base_url": "https://gateway.example.com",
            "token_username": "...",
            "token_password": "..."
        }
    },
}
```

`endpoint_id` and `part_id` are **not** part of this dict — `mcp_daemon_engine.execute_tool_function` sets them on the already-constructed `MCPSkillProvider` instance by splitting the caller's `partition_key` on `#` (`tool_obj.endpoint_id`, `tool_obj.part_id`). `connection_id` isn't consumed anywhere in this codebase.

### Standalone / local testing

There is currently no environment-variable override — `GraphQLClient` reads only the `setting` dict. To test locally, construct the provider directly with an explicit endpoint:

```python
provider = MCPSkillProvider(
    logger,
    graphql_modules={"harness_engineering": {"endpoint": "http://localhost:8000/graphql"}},
)
```

If a `HSK_GRAPHQL_ENDPOINT`-style env var fallback is wanted for local dev, it needs to be implemented in `graphql_client.py` — it is not there today.

---

## Delivery Plan

### P1 — Core module scaffold

**Duration:** 1 day

Deliver:
- `mcp_skill_provider` package with flat mixin layout
- `mcp_configuration.py` declaring all three tools
- `graphql_client.py` with `GraphQLClient` and `GraphQLModule` classes
- `graphql_backed_processor.py` with `GraphQLBackedProcessor` root base
- `skill_mixin.py` with `search_skills`, `get_skill`
- `command_mixin.py` with `run_command`
- `error_handler.py` with `@handle_errors` decorator and `ErrorCode` constants

**Exit criteria:**
- `MCPSkillProvider(logger, **setting)` instantiates without error
- `MCP_CONFIGURATION` lists `search_skills`, `get_skill`, `run_command`
- `SkillMixin.search_skills(query)` returns a normalized `{items, total}` dict
- `SkillMixin.get_skill(name)` returns a normalized snake_case skill dict
- `CommandMixin.run_command(name, argv)` delegates to Harness without executing locally

### P1.5 — Wire runtime registration for mcp_daemon_engine dispatch (done)

**Duration:** 0.5 day

Closed a prerequisite for P2 (see [Known Gaps](#known-gaps) item 1) — without it, `mcp_daemon_engine` had no way to route a tool call to `MCPSkillProvider`.

Delivered:
- `modules` block in `mcp_configuration.py` declaring `module_name: "mcp_skill_provider"`, `class_name: "mcp_skill_provider.mcp_skill_provider.MCPSkillProvider"`, `package_name: "mcp_skill_provider"`, `source: ""`, and a placeholder `setting.graphql_modules.harness_engineering` shape
- `module_links` block mapping each of `search_skills`, `get_skill`, `run_command` (`type: "tool"`) to that module and its matching `function_name`

**Exit criteria:**
- ✅ `mcp_daemon_engine.handlers.mcp_handlers.validate_manifest()` accepts the manifest without validation errors (verified directly against the live function)
- ⬜ A live `loadMcpConfiguration` call and a test invocation of `execute_tool_function` for `search_skills` still need to be run against a real (or local) `mcp_daemon_engine` instance — deferred to P2, since it requires a running daemon and a real GraphQL endpoint

**Note on `source=""`:** this means the package must already be importable from the daemon's `sys.path` (e.g. `pip install -e .`) — it will **not** be fetched from S3. If deployment moves to the S3 package-upload flow, `source` must change to `"s3"` and the package needs to be uploaded via `generateMcpPackageUploadUrl` / `processMcpPackage` first.

### P2 — Integration testing with mcp_daemon_engine

**Duration:** 2-3 days

Deliver:
- End-to-end tests using `mcp_daemon_engine`'s stdio transport
- Test the full `search_skills → get_skill → run_command` happy path
- Verify tenant identity is correctly inherited from gateway context

**Exit criteria:**
- An MCP client can call `mcp_daemon_engine` and invoke `search_skills`, `get_skill`, and `run_command` end-to-end
- A `run_command` call on a missing or disabled skill returns a clear error
- A non-allowlisted command is rejected before reaching the executor

---

## Dependencies

- [`mcp_daemon_engine`](../mcp_daemon_engine/) — MCP runtime host
- [`harness_engineering_engine`](../harness_engineering_engine/) — Skill catalog, deployment, and retrieval backend
- `mcp` — MCP SDK (tool schemas)
- `mcp_http_client` — HTTP client for external MCP servers (inherited by `mcp_daemon_engine`)

---

## Security Notes

- `run_command` never executes commands directly; it always delegates to `harness_engineering_engine.runCommand`, which performs allowlist validation, path normalization, and guarded execution server-side.
- The module does **not** accept arbitrary filesystem roots, environment variables, or execution policy overrides.
- Tenant identity is inherited from `mcp_daemon_engine` and the gateway context — never from user input.

---

## License

MIT
