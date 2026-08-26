# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Dict, List

import humps
from silvaengine_utility import convert_decimal_to_number

from .error_handler import (
    ErrorCode,
    ValidationError,
    build_error_response,
    handle_errors,
    no_result_message,
    propagate_error_if_present,
    validate_not_empty,
)
from .graphql_backed_processor import GraphQLBackedProcessor


class CommandMixin(GraphQLBackedProcessor):
    """MCP tools for guarded command execution.

    All commands are executed server-side by ``harness_engineering_engine``
    — this module never invokes subprocesses.
    """

    # * MCP Function.
    @handle_errors(operation_name="run command")
    def run_command(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an allowlisted command for a skill.

        Maps to GraphQL: runCommand mutation.

        ``run_command`` validates argv against the skill's ``allowed_commands``
        list server-side, runs without a shell, and enforces timeout + output caps.
        """
        name = arguments.get("name")
        argv = arguments.get("argv")
        workspace_scope = arguments.get("workspace_scope")

        if not name:
            raise ValidationError("name is required", ErrorCode.MISSING_REQUIRED_FIELD)
        if not argv or not isinstance(argv, list) or len(argv) == 0:
            raise ValidationError(
                "argv must be a non-empty list", ErrorCode.INVALID_ARGUMENTS
            )

        variables: Dict[str, Any] = {"name": name, "argv": argv}
        if workspace_scope:
            variables["workspaceScope"] = workspace_scope

        result = self._execute_graphql_query(
            "harness_graphql",
            "runCommand",
            "Mutation",
            variables,
        )

        if error := propagate_error_if_present(result):
            return error

        run_result = result.get("runCommand", {})

        # If the backend returned an error field, propagate it.
        if error := propagate_error_if_present(run_result):
            return error

        humps.decamelize(run_result)
        return run_result
