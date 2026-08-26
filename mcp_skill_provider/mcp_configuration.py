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
            "description": "Retrieve full instructions and metadata for a skill. Triggers on-demand local refresh from S3 when the local skill directory is missing or stale.",
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
            "description": "Execute an allowlisted command for a skill. argv is validated server-side against the skill's allowed_commands list. Runs without a shell, with timeout and output caps enforced.",
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
                },
                "required": ["name", "argv"],
            },
        },
    ],
    "modules": [
        {
            "module_name": "mcp_skill_provider",
            "class_name": "mcp_skill_provider.mcp_skill_provider.MCPSkillProvider",
            "package_name": "mcp_skill_provider",
            "source": "",
            # Default setting shape. Real endpoint/credential values are
            # supplied at registration time via loadMcpConfiguration's
            # `variables` argument, which overrides this wholesale.
            "setting": {
                "graphql_modules": {
                    "harness_engineering": {
                        "class_name": "harness_engineering_engine.main.HarnessEngineeringEngine",
                        "endpoint": "",
                        "x_api_key": "",
                        "gateway_base_url": "",
                        "token_username": "",
                        "token_password": "",
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
            "class_name": "mcp_skill_provider.mcp_skill_provider.MCPSkillProvider",
            "function_name": "search_skills",
        },
        {
            "name": "get_skill",
            "type": "tool",
            "module_name": "mcp_skill_provider",
            "class_name": "mcp_skill_provider.mcp_skill_provider.MCPSkillProvider",
            "function_name": "get_skill",
        },
        {
            "name": "run_command",
            "type": "tool",
            "module_name": "mcp_skill_provider",
            "class_name": "mcp_skill_provider.mcp_skill_provider.MCPSkillProvider",
            "function_name": "run_command",
        },
    ],
}
