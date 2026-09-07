#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP Configuration for mcp_skill_provider"""

__author__ = "bibow"

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
            # Default setting shape. Real endpoint/credential values are
            # supplied at registration time via loadMcpConfiguration's
            # `variables` argument, which overrides this wholesale.
            "setting": {
                "graphql_modules": {
                    "harness_engineering_engine": {
                        "class_name": "HarnessEngineeringEngine",
                        "endpoint": "",
                        "x_api_key": "",
                        "gateway_base_url": "",
                        "token_username": "",
                        "token_password": "",
                        # Timeout (seconds) for mutation operations that may
                        # take longer than the 60s query default — runCommand
                        # triggers a git-refresh on cache miss before executing
                        # the command. Override via loadMcpConfiguration variables.
                        "command_timeout_seconds": 120,
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
