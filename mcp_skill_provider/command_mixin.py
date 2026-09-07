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

        When ``background`` is True, the command is launched detached and a
        ``run_id`` is returned for polling via ``poll_command``.
        """
        name = arguments.get("name")
        argv = arguments.get("argv")
        workspace_scope = arguments.get("workspace_scope")
        background = arguments.get("background", False)

        if not name:
            raise ValidationError("name is required", ErrorCode.MISSING_REQUIRED_FIELD)
        if not argv or not isinstance(argv, list) or len(argv) == 0:
            raise ValidationError(
                "argv must be a non-empty list", ErrorCode.INVALID_ARGUMENTS
            )

        variables: Dict[str, Any] = {"name": name, "argv": argv}
        if workspace_scope:
            variables["workspaceScope"] = workspace_scope
        if background:
            variables["background"] = True

        result = self._execute_graphql_query(
            "harness_graphql",
            "runCommand",
            "Mutation",
            variables,
        )

        if error := propagate_error_if_present(result):
            return error

        # ``execute_query`` already unwraps ``data.runCommand`` — ``result``
        # *is* the runCommand payload, not an envelope containing it.
        run_result = humps.decamelize(result) if isinstance(result, dict) else result

        # If the backend returned an error field, propagate it.
        if error := propagate_error_if_present(run_result):
            return error

        return run_result

    # * MCP Function.
    @handle_errors(operation_name="poll command")
    def poll_command(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Poll the status of a background command launched by ``run_command``
        with ``background=true``.

        Maps to GraphQL: pollCommand query.
        """
        run_id = arguments.get("run_id")

        if not run_id:
            raise ValidationError("run_id is required", ErrorCode.MISSING_REQUIRED_FIELD)

        variables = {"run_id": run_id}

        result = self._execute_graphql_query(
            "harness_graphql",
            "pollCommand",
            "Query",
            variables,
        )

        if error := propagate_error_if_present(result):
            return error

        # ``execute_query`` already unwraps ``data.pollCommand`` — ``result``
        # *is* the pollCommand payload, not an envelope containing it.
        poll_result = humps.decamelize(result) if isinstance(result, dict) else result

        if error := propagate_error_if_present(poll_result):
            return error

        return poll_result
