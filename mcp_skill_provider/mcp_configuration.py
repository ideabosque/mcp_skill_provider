#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP Configuration for mcp_skill_provider"""

__author__ = "bibow"

import os


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


_GATEWAY_BASE_URL = os.getenv("MCP_SKILL_PROVIDER_GATEWAY_BASE_URL") or os.getenv(
    "BASE_URL", "http://localhost:8765"
)
_HARNESS_GRAPHQL_ENDPOINT = os.getenv(
    "MCP_SKILL_PROVIDER_HARNESS_GRAPHQL_ENDPOINT",
    f"{_GATEWAY_BASE_URL.rstrip('/')}/{{endpoint_id}}/harness_graphql",
)

MCP_CONFIGURATION = {
    "tools": [
        {
            "name": "search_skills",
            "description": "Search enabled skills by name and description. Returns a ranked list of matching skills.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 10)",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_skill",
            "description": "Retrieve full instructions and metadata for a skill. Read the returned `body` for instructions, then call `run_command` with an `argv` that matches one of the `allowed_commands` entries. The response also includes `cli_packages` (declared dependencies) and `references` (file contents the skill references). Triggers on-demand git refresh when the local skill directory is missing or stale — if a refresh is in progress, the response includes `status: \"refreshing\"` with an empty body; retry after a short wait to get the full content.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill name identifier",
                    },
                },
                "required": ["name"],
            },
        },
        {
            "name": "run_command",
            "description": "Execute an allowlisted command for a skill. argv is validated server-side against the skill's allowed_commands list. Runs without a shell, with a timeout (default 30s) and output caps (default 20KB) enforced. Commands exceeding the timeout are killed and return timed_out=true; output exceeding the cap is truncated. For long-running scripts (over 30s), set background=true to launch the command detached — the response returns a run_id immediately; poll for results using the poll_command tool with that run_id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Skill name identifier",
                    },
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Structured argv list (no shell strings)",
                    },
                    "workspace_scope": {
                        "type": "string",
                        "description": "Optional workspace scope (e.g. skill_dir, workspace_dir)",
                    },
                    "background": {
                        "type": "boolean",
                        "description": "Launch the command detached in the background. Returns a run_id immediately for polling via poll_command. Use for commands that may take longer than 30s.",
                    },
                },
                "required": ["name", "argv"],
            },
        },
        {
            "name": "poll_command",
            "description": "Poll the status of a background command launched by run_command with background=true. Returns status (running, completed, timed_out, not_found), stdout, stderr, exit_code, timed_out, and truncated. Poll periodically until status is no longer 'running'.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "The run_id returned by run_command with background=true",
                    },
                },
                "required": ["run_id"],
            },
        },
    ],
    "modules": [
        {
            "module_name": "mcp_skill_provider",
            "class_name": "MCPSkillProvider",
            "package_name": "mcp_skill_provider",
            "source": "",
            # Default setting shape. Values come from the gateway environment
            # during Git deployment, so the generic deploy_mcp_git.py script can
            # install this package without a one-off variables wrapper.
            # loadMcpConfiguration variables can still override this wholesale.
            "setting": {
                "graphql_modules": {
                    "harness_engineering_engine": {
                        "class_name": "HarnessEngineeringEngine",
                        "endpoint": _HARNESS_GRAPHQL_ENDPOINT,
                        "x_api_key": os.getenv(
                            "MCP_SKILL_PROVIDER_HARNESS_X_API_KEY",
                            os.getenv("x-api-key", ""),
                        ),
                        "gateway_base_url": _GATEWAY_BASE_URL,
                        "token_username": os.getenv(
                            "MCP_SKILL_PROVIDER_TOKEN_USERNAME",
                            os.getenv("ADMIN_USERNAME", ""),
                        ),
                        "token_password": os.getenv(
                            "MCP_SKILL_PROVIDER_TOKEN_PASSWORD",
                            os.getenv("ADMIN_PASSWORD", ""),
                        ),
                        # Timeout (seconds) for mutation operations that may
                        # take longer than the 60s query default — runCommand
                        # triggers a git-refresh on cache miss before executing.
                        "command_timeout_seconds": _int_env(
                            "MCP_SKILL_PROVIDER_COMMAND_TIMEOUT_SECONDS", 120
                        ),
                    }
                }
            },
        }
    ],
    "module_links": [
        {
            "name": "search_skills",
            "type": "tool",
            "module_name": "mcp_skill_provider",
            "class_name": "MCPSkillProvider",
            "function_name": "search_skills",
        },
        {
            "name": "get_skill",
            "type": "tool",
            "module_name": "mcp_skill_provider",
            "class_name": "MCPSkillProvider",
            "function_name": "get_skill",
        },
        {
            "name": "run_command",
            "type": "tool",
            "module_name": "mcp_skill_provider",
            "class_name": "MCPSkillProvider",
            "function_name": "run_command",
        },
        {
            "name": "poll_command",
            "type": "tool",
            "module_name": "mcp_skill_provider",
            "class_name": "MCPSkillProvider",
            "function_name": "poll_command",
        },
    ],
}
