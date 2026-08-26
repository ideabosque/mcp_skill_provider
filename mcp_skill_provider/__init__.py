#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP Skill Provider — Harness Engineering MCP Server."""

from __future__ import annotations

__author__ = "bibow"
__version__ = "0.0.1"

from .mcp_configuration import MCP_CONFIGURATION
from .mcp_skill_provider import MCPSkillProvider

__all__ = ["MCPSkillProvider", "MCP_CONFIGURATION"]
