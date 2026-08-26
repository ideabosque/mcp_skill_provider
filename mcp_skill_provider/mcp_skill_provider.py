#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP Skill Provider — Harness Engineering MCP Server Facade.

Flat mixin composition: all domain mixins inherit only from
GraphQLBackedProcessor and are composed into this single facade class
that the MCP runtime instantiates.
"""
from __future__ import annotations

__author__ = "bibow"

import logging
from typing import Any, Dict

from .command_mixin import CommandMixin
from .graphql_backed_processor import GraphQLBackedProcessor
from .skill_mixin import SkillMixin


class MCPSkillProvider(
    SkillMixin,
    CommandMixin,
):
    """Public interface aggregating all Harness Engineering MCP tools.

    Flat composition replaces the original deep inheritance chain.
    Each mixin contributes its own MCP tool methods and only accesses
    ``self.logger``, ``self.setting``, and ``self._execute_graphql_query``
    (all provided by GraphQLBackedProcessor).
    """

    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]):
        GraphQLBackedProcessor.__init__(self, logger, **setting)
