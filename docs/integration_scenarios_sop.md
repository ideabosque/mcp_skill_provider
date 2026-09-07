# Continuous Integration Scenarios SOP — mcp_skill_provider

> **Status:** DRAFT — pre-filled from project discovery on 2026-09-06.
> Items still marked `<needs input>` require user confirmation before this SOP
> is approved and test execution (Phase 8+) may begin.

---

## 1. Document Control

| Field | Value |
|---|---|
| SOP title | mcp_skill_provider CI Integration SOP |
| Version | 0.1.0 (draft) |
| Owner / contact | `<needs input — name, email>` |
| Last updated | 2026-09-06 |
| Business domain | generic (MCP tool provider module — no ecommerce/logistics domain model) |
| Target environment | dev |
| Approval status | approved |

## 2. Purpose and Scope

This SOP certifies that `mcp_skill_provider` correctly exposes Harness Engineering skill tools through `mcp_daemon_engine` and that every tool call is correctly routed, authenticated, and delegated to the `harness_engineering_engine` GraphQL backend. Certification is needed now because the package scaffold (P1/P1.5) is complete but no integration tests exist yet (P2 not started).

- **In scope:**
  - `MCPSkillProvider` facade and its four MCP tools: `search_skills`, `get_skill`, `run_command`, `poll_command`
  - `GraphQLClient` HTTP/2 transport, JWT Bearer and `x-api-key` authentication, 401 retry
  - `MCP_CONFIGURATION` manifest correctness (`tools`, `modules`, `module_links`)
  - End-to-end dispatch: MCP client → `mcp_daemon_engine` → `MCPSkillProvider` → `harness_engineering_engine` GraphQL
  - Error handling and validation paths (`@handle_errors`, `ErrorCode` constants, `propagate_error_if_present`)
  - `humps.decamelize` normalization of GraphQL camelCase → snake_case
- **Out of scope:**
  - `harness_engineering_engine` internal logic (covered by its own 155-test suite)
  - `mcp_daemon_engine` core runtime (covered by its own tests)
  - `mcp_http_client` request timeout (tracked separately as G-7 in DEVELOPMENT_PLAN.md)
  - Unit tests for this package's own modules (tracked as gap 6; this SOP covers integration, not unit coverage)
- **System(s) under test:** `mcp_skill_provider` module + its dependencies: `mcp_daemon_engine` (MCP runtime host) and `harness_engineering_engine` (GraphQL backend)

> **Existing test coverage note:** `harness_engineering_engine/tests/test_mcp_integration.py` already covers INT-001 through INT-012 at the **GraphQL schema layer** (in-process `Schema.execute`, no HTTP transport, no `mcp_skill_provider` code involved). The scenarios in this SOP focus on the **provider layer** — exercising `MCPSkillProvider`'s mixin methods, `GraphQLClient` HTTP/2 transport, JWT/x-api-key auth, `humps.decamelize` normalization, `@handle_errors` error wrapping, and `MCP_CONFIGURATION` manifest validation. Where scenarios overlap with the backend tests, the provider tests validate the *seam* between this module and the backend (HTTP call, response shape transformation, error propagation), not the backend logic itself.

## 3. Environment and Access

| Item | Value / source |
|---|---|
| Environment target | dev |
| Base URLs / endpoints | `silvaengine_gateway` at `http://localhost:8765` (local dev); `harness_engineering_engine` GraphQL route through gateway: `http://localhost:8765/{endpoint_id}/harness_engineering_graphql` with `endpoint_id=gpt`. `mcp_daemon_engine` SSE transport at `http://localhost:8000` (local dev). |
| Credential source | `silvaengine_gateway/tests/.env` — local auth provider (`GATEWAY_AUTH_PROVIDER=local`), admin credentials `ADMIN_USERNAME=admin` / `ADMIN_PASSWORD=admin123`, JWT secret in `.env`. `x-api-key=silvaengine` for API-key fallback. Never inline in this SOP — read from the `.env` at runtime. |
| Required env vars | None implemented today — `HSK_GRAPHQL_ENDPOINT` is documented but **not wired** (Known Gap 2). All config flows through the `setting` dict supplied at `loadMcpConfiguration` time. |
| Data stores | Backend-owned: PostgreSQL (`localhost:5432`, db=`silvaengine`, schema=`silvaengine`, table prefix `hsk_`); local skill cache at `harness_engineering_engine/skills/`. This module holds no data. |
| Messaging / events | None — this module is synchronous GraphQL only |
| Access constraints | localhost dev environment — no VPN/IP allowlist needed. AWS credentials in `.env` for DynamoDB fallback (`us-west-2`). |
| Provisioning policy | manual approval required (no auto-provisioning — this module has no schema/data of its own) |

> List **names and sources only** — never paste secrets, tokens, or connection strings.

## 4. Dependency Readiness Requirements

> Each dependency must reach all four readiness states before testing begins:
> `available -> configured -> initialized -> operational`.

| Dependency | Type (internal / infra / external) | Health check | Required readiness | Owner |
|---|---|---|---|---|
| `mcp_daemon_engine` | internal | stdio/SSE transport accepts `loadMcpConfiguration`; `execute_tool_function` routes tool calls | operational | SilvaEngine team (bibow) |
| `harness_engineering_engine` | internal | GraphQL endpoint responds to introspection / `searchSkills` query | operational | SilvaEngine team (bibow) |
| `silvaengine_gateway` | external | `/auth/token` endpoint issues JWT for `token_username`/`token_password` | operational | SilvaEngine team (bibow) |
| `httpx[http2]` | infrastructure (library) | import succeeds; HTTP/2 connection to GraphQL endpoint establishes | configured | n/a |
| `silvaengine_utility` | infrastructure (library) | import succeeds; `Graphql`, `Serializer`, `convert_decimal_to_number` available | configured | n/a |
| `pyhumps` | infrastructure (library) | import succeeds; `humps.decamelize` callable | configured | n/a |

## 5. Test Data Requirements

This module holds no data — all test data lives in `harness_engineering_engine`. Test assets are skill catalog entries that must exist in the backend before integration tests run.

| Asset type | Count | Notes / constraints |
|---|---|---|
| Enabled skills | ≥ 3 | At least one with `allowed_commands` (for `run_command`), one without (for negative path). DB has 7 enabled skills under `partition_key=gpt#nestaging` (all `deployment_status=deployed`, `enabled=true`, `is_active=true`). |
| Disabled / missing skills | 1 | For `get_skill` not-found and `run_command` denied paths. Use a non-existent name (e.g. `nonexistent-skill-xyz`). |
| Skills with `cli_packages` | ≥ 1 | To verify P9 `cli_packages` + `references` fields are surfaced. `hsk_cli_packages` table has 1 row under `gpt#nestaging`. |
| Skills with long-running commands | 1 | To exercise `background=true` + `poll_command` flow. Skills use `msv` CLI commands (e.g. `msv pipeline status`); a longer-running one can be used or a test skill deployed with a sleep script. |
| Users / roles | 1 | Admin user: `username=admin`, `password=admin123` (local auth). `partition_key=gpt#nestaging`, `endpoint_id=gpt`. |

- **Load order:** no local loading — backend skill catalog must be pre-seeded. Verify via `search_skills` before testing.
- **Data source:** existing `harness_engineering_engine` skill catalog in PostgreSQL (`hsk_skills` table, `partition_key=gpt#nestaging`). 7 skills currently deployed: `gsap-animation-authoring`, `motion-design-principles`, `multilingual-rollout`, `slide-deck-localization`, `slide-video-orchestration`, `slideshow-video-production`, `youtube-video-publishing`. Additional test-only skills (e.g. `echo-skill` with `allowed_commands=[["python","--version"]]`) can be deployed via `deploySkillPackage` mutation against a temp git repo — see `harness_engineering_engine/tests/test_mcp_integration.py` for the pattern.

## 6. Execution Order

> This module is a stateless pass-through with four tools and no internal data
> dependency chain. The order below follows the logical call sequence an agent
> would use, not a domain entity lifecycle.

```text
Manifest validation → Module import/instantiation → Auth (JWT acquisition)
  → search_skills (Query) → get_skill (Query) → run_command (Mutation)
  → poll_command (Query) → Error/resilience paths → Reconciliation
```

**Reason for deviation from default sequence:** The skill default
(`Foundation → Master Data → Customer → ... → Billing`) applies to domain
entity lifecycles. `mcp_skill_provider` has no domain entities — it is a
stateless GraphQL proxy with four tools. The order above mirrors the
agent workflow (`search → retrieve → execute → poll`) and places error
paths after the happy path.

## 7. Integration Scenarios

### Scenario INT-001: Manifest validation

| Field | Value |
|---|---|
| **ID** | INT-001 |
| **Name** | MCP_CONFIGURATION manifest is valid and accepted by mcp_daemon_engine |
| **Priority** | P1 |
| **Type** | API |
| **CI trigger** | on pull request |
| **Preconditions** | `mcp_daemon_engine` importable; `mcp_skill_provider` installed (`pip install -e .`) |
| **Dependencies** | mcp_daemon_engine |
| **Test data** | none |
| **Steps** | 1. Import `MCP_CONFIGURATION` from `mcp_skill_provider`. 2. Call `mcp_daemon_engine.handlers.mcp_handlers.validate_manifest()` with it. |
| **Expected behavior** | `validate_manifest` passes with no errors; `tools` lists 4 tools; `modules` has 1 module; `module_links` maps all 4 tools to `MCPSkillProvider` |
| **Validation points** | manifest_valid, tool_count=4, module_links_count=4 |
| **Cross-system checks** | each `module_links` entry's `function_name` resolves to a method on `MCPSkillProvider` |

### Scenario INT-002: Module instantiation

| Field | Value |
|---|---|
| **ID** | INT-002 |
| **Name** | MCPSkillProvider instantiates with a setting dict and constructs GraphQLClient |
| **Priority** | P1 |
| **Type** | API |
| **CI trigger** | on pull request |
| **Preconditions** | INT-001 passed |
| **Dependencies** | none (unit-level) |
| **Test data** | minimal `setting` dict with `graphql_modules.harness_engineering_engine.endpoint` |
| **Steps** | 1. Construct `MCPSkillProvider(logger, **setting)` with a test endpoint. 2. Assert `self.graphql_client` is a `GraphQLClient`. 3. Assert `self.logger` and `self.setting` are set. |
| **Expected behavior** | No exception; `graphql_client.graphql_modules` lazily creates `harness_engineering_engine` module on access |
| **Validation points** | instance_created, graphql_client_present |
| **Cross-system checks** | none |

### Scenario INT-003: Auth — JWT Bearer token acquisition

| Field | Value |
|---|---|
| **ID** | INT-003 |
| **Name** | GraphQLModule obtains a JWT from silvaengine_gateway and attaches it as Bearer |
| **Priority** | P1 |
| **Type** | API |
| **CI trigger** | nightly |
| **Preconditions** | `silvaengine_gateway` `/auth/token` endpoint reachable; valid `token_username`/`token_password` in setting |
| **Dependencies** | silvaengine_gateway |
| **Test data** | gateway credentials in `setting` (never inline) |
| **Steps** | 1. Access `graphql_module.get_gateway_token()`. 2. Verify a non-empty token string is returned. 3. Verify `auth_mode == "jwt"`. 4. Verify `_jwt_expiry(token)` returns a future timestamp. |
| **Expected behavior** | Token acquired; cached for subsequent calls; re-auth triggers within `_TOKEN_EXPIRY_SKEW_SECONDS` (60s) of expiry |
| **Validation points** | token_acquired, auth_mode_jwt, expiry_in_future |
| **Cross-system checks** | token parses as valid JWT with `exp` claim |

### Scenario INT-004: search_skills happy path

| Field | Value |
|---|---|
| **ID** | INT-004 |
| **Name** | search_skills returns ranked, decamelized skill list from backend |
| **Priority** | P1 |
| **Type** | API (end-to-end through GraphQL) |
| **CI trigger** | on pull request |
| **Preconditions** | INT-003 passed; backend has ≥ 3 enabled skills |
| **Dependencies** | harness_engineering_engine, silvaengine_gateway |
| **Test data** | a query string matching at least one enabled skill (e.g. `python` or `slide` — matches `slide-deck-localization`, `slide-video-orchestration`, `slideshow-video-production`) |
| **Steps** | 1. Call `search_skills(query="<known skill name>", limit=10)`. 2. Inspect the returned `items`. |
| **Expected behavior** | 200; `items` is a list with ≥ 1 result; each item's keys are snake_case (decamelized); `total` ≥ 1 |
| **Validation points** | results_returned, snake_case_keys, ranking_relevant |
| **Cross-system checks** | returned skill names match backend `searchSkills` resolver output |

### Scenario INT-005: get_skill happy path

| Field | Value |
|---|---|
| **ID** | INT-005 |
| **Name** | get_skill returns full skill body, allowed_commands, cli_packages, references |
| **Priority** | P1 |
| **Type** | API (end-to-end) |
| **CI trigger** | on pull request |
| **Preconditions** | INT-004 returned a skill name; skill is enabled and cached |
| **Dependencies** | harness_engineering_engine |
| **Test data** | skill name from INT-004 (e.g. `slideshow-video-production`) |
| **Steps** | 1. Call `get_skill(name="<skill from INT-004>")`. 2. Inspect `body`, `allowed_commands`, `cli_packages`, `references`. |
| **Expected behavior** | `body` is non-empty markdown; `allowed_commands` is a list; keys are snake_case |
| **Validation points** | skill_returned, body_non_empty, allowed_commands_present |
| **Cross-system checks** | skill `name` matches the requested name |

### Scenario INT-006: get_skill — refreshing status

| Field | Value |
|---|---|
| **ID** | INT-006 |
| **Name** | get_skill returns error with OPERATION_FAILED when backend reports status="refreshing" |
| **Priority** | P2 |
| **Type** | API |
| **CI trigger** | nightly |
| **Preconditions** | A skill whose local cache is stale/missing so backend triggers git refresh |
| **Dependencies** | harness_engineering_engine |
| **Test data** | skill name known to be stale (or one never requested before — e.g. `youtube-video-publishing` if never fetched, or deploy a fresh test skill and corrupt its `.hsk-skill.json` checksum) |
| **Steps** | 1. Call `get_skill(name="<stale skill>")`. 2. If response contains `status: "refreshing"`, verify error response. 3. Retry after wait — expect full content on second call. |
| **Expected behavior** | First call returns `{error: "...Retry get_skill...", error_code: "OPERATION_FAILED"}`; retry returns full body |
| **Validation points** | refreshing_status_surfaced, retry_succeeds |
| **Cross-system checks** | none |

### Scenario INT-007: run_command happy path (synchronous)

| Field | Value |
|---|---|
| **ID** | INT-007 |
| **Name** | run_command executes an allowlisted command server-side and returns stdout/stderr |
| **Priority** | P1 |
| **Type** | end-to-end (Mutation) |
| **CI trigger** | pre-release |
| **Preconditions** | INT-005 passed; skill has `allowed_commands` with a simple, safe command (e.g. `echo`) |
| **Dependencies** | harness_engineering_engine |
| **Test data** | skill name + argv matching an `allowed_commands` entry. Deploy a test skill (e.g. `echo-skill` with `allowed_commands=[["python","--version"]]`) via `deploySkillPackage`, or use `msv pipeline status --run-id <id>` against an existing skill if a run-id is available. |
| **Steps** | 1. Call `run_command(name="<skill>", argv=["echo", "hello"])`. 2. Inspect `stdout`, `stderr`, `exit_code`. |
| **Expected behavior** | `exit_code == 0`; `stdout` contains "hello"; keys are snake_case |
| **Validation points** | command_executed, exit_code_zero, output_returned |
| **Cross-system checks** | command ran on backend, never locally (no local subprocess spawned) |

### Scenario INT-008: run_command background + poll_command

| Field | Value |
|---|---|
| **ID** | INT-008 |
| **Name** | run_command with background=true returns run_id; poll_command retrieves result |
| **Priority** | P1 |
| **Type** | end-to-end (Mutation + Query) |
| **CI trigger** | pre-release |
| **Preconditions** | INT-007 passed; skill has a command that takes > 1s |
| **Dependencies** | harness_engineering_engine |
| **Test data** | skill name + argv for a short sleep or multi-step script. Deploy a test skill with `allowed_commands=[["python", "<script_path>"]]` where the script sleeps ~2s (see `test_mcp_integration.py` INT-006 pattern). |
| **Steps** | 1. Call `run_command(name="<skill>", argv=[...], background=True)`. 2. Assert `run_id` returned. 3. Poll `poll_command(run_id=<id>)` until status != "running". 4. Inspect final `stdout`/`exit_code`. |
| **Expected behavior** | Immediate `run_id`; poll eventually returns `status: "completed"`, `exit_code: 0` |
| **Validation points** | run_id_returned, poll_completes, final_output_present |
| **Cross-system checks** | none |

### Scenario INT-009: run_command — non-allowlisted command rejected

| Field | Value |
|---|---|
| **ID** | INT-009 |
| **Name** | run_command with an argv not in allowed_commands is rejected by backend |
| **Priority** | P1 |
| **Type** | API (error path) |
| **CI trigger** | on pull request |
| **Preconditions** | INT-005 passed |
| **Dependencies** | harness_engineering_engine |
| **Test data** | skill name + argv that does NOT match any `allowed_commands` entry |
| **Steps** | 1. Call `run_command(name="<skill>", argv=["rm", "-rf", "/"])`. 2. Inspect error response. |
| **Expected behavior** | Error response with `error_code` indicating denial (COMMAND_DENIED or backend equivalent); no command executed |
| **Validation points** | command_denied, no_side_effects |
| **Cross-system checks** | backend command executor logs the denial |

### Scenario INT-010: x-api-key auth fallback

| Field | Value |
|---|---|
| **ID** | INT-010 |
| **Name** | When no JWT credentials are configured, GraphQLClient falls back to x-api-key header |
| **Priority** | P2 |
| **Type** | API |
| **CI trigger** | nightly |
| **Preconditions** | `setting` has `x_api_key` but no `gateway_base_url`/`token_username`/`token_password` |
| **Dependencies** | harness_engineering_engine |
| **Test data** | valid `x_api_key` for the backend |
| **Steps** | 1. Construct provider with only `x_api_key`. 2. Call `search_skills`. 3. Verify `auth_mode == "api_key"`. |
| **Expected behavior** | Request sent with `x-api-key` header; response successful |
| **Validation points** | auth_mode_api_key, request_succeeds |
| **Cross-system checks** | none |

### Scenario INT-011: 401 retry with token invalidation

| Field | Value |
|---|---|
| **ID** | INT-011 |
| **Name** | On 401/403 with JWT auth, client invalidates token, re-authenticates, and retries once |
| **Priority** | P2 |
| **Type** | API (resilience) |
| **CI trigger** | nightly |
| **Preconditions** | JWT auth configured; a way to force a 401 (expired token or revoked) |
| **Dependencies** | silvaengine_gateway |
| **Test data** | an expired or invalid `gateway_token` in setting |
| **Steps** | 1. Seed `gateway_token` with an expired JWT. 2. Call `search_skills`. 3. Observe the retry. |
| **Expected behavior** | First request gets 401; client calls `invalidate_gateway_token` + `get_gateway_token`; second request succeeds |
| **Validation points** | token_invalidated, reauth_triggered, retry_succeeds |
| **Cross-system checks** | two POST requests to GraphQL endpoint (one 401, one 200) |

### Scenario INT-012: Mutation timeout budget (command_timeout_seconds)

| Field | Value |
|---|---|
| **ID** | INT-012 |
| **Name** | runCommand mutation uses configurable timeout (default 120s), not the 60s query default |
| **Priority** | P3 |
| **Type** | API (configuration) |
| **CI trigger** | pre-release |
| **Preconditions** | INT-007 passed |
| **Dependencies** | harness_engineering_engine |
| **Test data** | setting with `command_timeout_seconds: 180` |
| **Steps** | 1. Construct provider with `command_timeout_seconds: 180`. 2. Call `run_command`. 3. Inspect httpx timeout used. |
| **Expected behavior** | Mutation uses 180s timeout; queries still use 60s |
| **Validation points** | timeout_override_applied |
| **Cross-system checks** | none |

## 8. Failure and Resilience Scenarios

| Scenario | Injected fault | Expected behavior |
|---|---|---|
| `missing_data` | `get_skill(name="<nonexistent>")` | Error response with `error_code: SKILL_NOT_FOUND` |
| `missing_data` | `search_skills(query="<no match>")` | Error response with `error_code: NO_SKILLS_FOUND` |
| `invalid_data` | `search_skills(query="")` | `ValidationError` with `error_code: VALIDATION_FAILED` (from `validate_not_empty`) |
| `invalid_data` | `run_command(name=None, argv=[])` | `ValidationError` with `error_code: MISSING_REQUIRED_FIELD` / `INVALID_ARGUMENTS` |
| `invalid_data` | `poll_command(run_id=None)` | `ValidationError` with `error_code: MISSING_REQUIRED_FIELD` |
| `api_failures` | GraphQL backend returns `errors` in response | `GraphQLClient` raises, `@handle_errors` catches, returns `{error, error_code: GRAPHQL_QUERY_FAILED}` |
| `api_failures` | GraphQL endpoint unreachable (connection refused) | httpx raises; `@handle_errors` returns `GRAPHQL_QUERY_FAILED` with extracted message |
| `authentication_failures` | 401 on first request, JWT auth | Token invalidated + re-auth + single retry (INT-011) |
| `authentication_failures` | 401 on retry too | Second 401 propagated as error response (no infinite retry loop) |
| `third_party_outages` | `silvaengine_gateway` `/auth/token` down | `get_gateway_token` raises; error propagated |
| `service_outages` | `harness_engineering_engine` down | httpx connect timeout (15s); error response returned |

## 9. Data Reconciliation Checks

> This module is stateless — reconciliation is about response shape consistency
> between what the backend returns (camelCase) and what the MCP caller receives
> (snake_case), plus error-code correctness.

| Check | Rule | Tolerance |
|---|---|---|
| Decamelization consistency | Every GraphQL response field is snake_case before reaching the MCP caller | 0 un-decamelized keys |
| Error envelope consistency | Every error path returns `{error, error_code}` dict (never raises to MCP caller) | 0 uncaught exceptions |
| Manifest ↔ implementation parity | Every `module_links` `function_name` exists as a method on `MCPSkillProvider` | 0 missing methods |
| Tool schema ↔ method signature parity | Every `inputSchema.required` field is validated in the method body | 0 missing validations |
| Timeout correctness | Mutations use `command_timeout_seconds`; queries use 60s | 0 misrouted timeouts |

## 10. Entry and Exit Criteria

**Entry criteria (testing may begin when):**
- `mcp_daemon_engine` importable and stdio transport functional
- `harness_engineering_engine` GraphQL endpoint reachable from the test environment
- `silvaengine_gateway` `/auth/token` reachable (if JWT auth path is tested)
- `mcp_skill_provider` installed (`pip install -e .`) and importable
- Backend skill catalog pre-seeded with ≥ 3 enabled skills (≥ 1 with `allowed_commands`)
- Target environment confirmed by user

**Exit criteria (certification may be issued when):**
- All P1 scenarios (INT-001, 002, 003, 004, 005, 007, 008, 009) pass
- Coverage ≥ 80% of declared scenarios executed
- No blocking defects remain
- Decamelization and error-envelope reconciliation checks clean
- 401 retry path verified (INT-011) if JWT auth is in scope

## 11. CI Trigger and Cadence

| Trigger | Scope run | Required to pass |
|---|---|---|
| On pull request | INT-001, INT-002, INT-004, INT-005, INT-007, INT-009 (P1 smoke + manifest + happy + denial) | yes — blocks merge |
| Nightly | P1 + P2 (add INT-003, INT-006, INT-010, INT-011) | report only |
| Pre-release | Full suite (INT-001 through INT-012) + resilience + reconciliation | yes — blocks release |

> No CI pipeline (GitHub Actions, etc.) exists yet in this monorepo — no `.github/workflows/` found. Tests are run manually via `pytest` or the `run_integration.py` script in `harness_engineering_engine/tests/`. A CI pipeline should be set up as a follow-up; until then, the triggers above describe the intended cadence, executed manually.

## 12. Reporting and Certification Expectations

- **Report format:** markdown (default per `skill-config.yaml`)
- **Required certification decision:** one of `Integration Certified`, `Ready for UAT`, `Ready for Production`, `Ready with Conditions`, `Not Ready`
- **Report location:** `docs/test_results/` in this project (e.g. `docs/test_results/integration_certification_report.md`)
- **Distribution:** SilvaEngine development team (bibow) — `<needs input — additional recipients?>`

## 13. Sign-off

| Role | Name | Date | Decision |
|---|---|---|---|
| Test owner | `<needs input>` | `<needs input>` | `<needs input>` |
| Release manager | `<needs input>` | `<needs input>` | `<needs input>` |

---

## Open Items Requiring User Input

The following placeholders must be resolved before this SOP can be approved and
test execution (Phase 8+) begins:

1. **Owner / contact** (Section 1) — name and email for this SOP.
2. **Report distribution** (Section 12) — additional recipients beyond SilvaEngine dev team?
3. **Sign-off roles** (Section 13) — names for test owner and release manager.
4. **Scope confirmation** — do you want the full 13-phase certification, or a subset (e.g. through Phase 9 = test suite generation only)?

### Resolved from user input (2026-09-06)

- **Target environment**: dev
- **GraphQL endpoint**: `silvaengine_gateway` at `http://localhost:8765`, route `/{endpoint_id}/harness_engineering_graphql` with `endpoint_id=gpt`
- **Access constraints**: localhost dev — no VPN/IP allowlist needed
- **Dependency owners**: all owned by SilvaEngine team (bibow)
- **Tenant test user**: admin user from `silvaengine_gateway/tests/.env` (`admin`/`admin123`, `partition_key=gpt#nestaging`)
- **Backend skill catalog**: 7 enabled skills in `hsk_skills` table under `gpt#nestaging` (PostgreSQL `localhost:5432/silvaengine`); 1 `hsk_cli_packages` row
- **CI pipeline**: none exists yet — tests run manually via `pytest`; CI setup is a follow-up