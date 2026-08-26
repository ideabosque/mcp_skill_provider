# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Dict

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


class SkillMixin(GraphQLBackedProcessor):
    """MCP tools for skill discovery and retrieval."""

    # * MCP Function.
    @handle_errors(operation_name="search skills")
    def search_skills(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search skills by name and description.

        Maps to GraphQL: searchSkills query
        """
        variables = {
            "query": arguments.get("query", ""),
            "limit": arguments.get("limit", 10),
        }
        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        validate_not_empty(variables.get("query"), "query")

        result = self._execute_graphql_query(
            "harness_graphql",
            "searchSkills",
            "Query",
            variables,
        )

        if error := propagate_error_if_present(result):
            return error

        skills = result.get("searchSkills", {})
        for skill in skills.get("items", []):
            humps.decamelize(skill)

        message = no_result_message(skills, "No skills found matching the query.")
        if message:
            return build_error_response(message, ErrorCode.NO_SKILLS_FOUND)
        return skills

    # * MCP Function.
    @handle_errors(operation_name="get skill")
    def get_skill(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get full instructions and metadata for a skill.

        Maps to GraphQL: skill query.  Triggers on-demand local refresh from
        S3 when the local skill directory is missing or stale.
        """
        variables = {"name": arguments.get("name")}

        if not variables.get("name"):
            raise ValidationError("name is required", ErrorCode.MISSING_REQUIRED_FIELD)

        result = self._execute_graphql_query(
            "harness_graphql",
            "skill",
            "Query",
            variables,
        )

        if error := propagate_error_if_present(result):
            return error

        skill = result.get("skill")
        if skill is None:
            return build_error_response(
                f"Skill '{variables['name']}' not found.",
                ErrorCode.SKILL_NOT_FOUND,
            )

        humps.decamelize(skill)
        return skill
