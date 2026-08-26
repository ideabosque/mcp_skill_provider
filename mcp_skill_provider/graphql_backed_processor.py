# -*- coding: utf-8 -*-
"""Base processor providing GraphQL execution for all skill mixins."""
from __future__ import annotations

__author__ = "bibow"

import logging
from typing import Any, Dict

from .graphql_client import GraphQLClient


class GraphQLBackedProcessor:
    """Root base class for all MCP skill mixins.

    Provides ``self.logger``, ``self.setting``, ``self.graphql_client``,
    and the ``_execute_graphql_query`` method that every mixin uses to
    communicate with the ``harness_engineering_engine`` backend.
    """

    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]):
        self.logger = logger
        self.setting = setting
        self.graphql_client = GraphQLClient(logger, **setting)

    @property
    def endpoint_id(self) -> str | None:
        return self.graphql_client.endpoint_id

    @endpoint_id.setter
    def endpoint_id(self, value: str):
        self.graphql_client.endpoint_id = value

    @property
    def part_id(self) -> str | None:
        return self.graphql_client.part_id

    @part_id.setter
    def part_id(self, value: str):
        self.graphql_client.part_id = value

    def _execute_graphql_query(
        self,
        function_name: str,
        operation_name: str,
        operation_type: str,
        variables: Dict[str, Any],
        query: str = None,
    ) -> Dict[str, Any]:
        return self.graphql_client.execute_query(
            function_name, operation_name, operation_type, variables, query=query
        )
