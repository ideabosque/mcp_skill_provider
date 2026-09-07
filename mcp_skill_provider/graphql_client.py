# -*- coding: utf-8 -*-
"""GraphQL client for mcp_skill_provider.

Handles GraphQL query execution via HTTP/2 against the
``harness_engineering_engine`` backend.  Auth supports silvaengine_gateway
JWT Bearer or AWS API Gateway ``x-api-key``.
"""
from __future__ import annotations

__author__ = "bibow"

import base64
import json
import logging
import time
import traceback
from typing import Any, Dict

import httpx
import humps

from silvaengine_utility.graphql import Graphql
from silvaengine_utility.serializer import Serializer

from .error_handler import (
    ErrorCode,
    GraphQLError,
    build_error_response,
    extract_error_message,
)

# Seconds of safety margin before a JWT's ``exp`` at which the client proactively
# re-authenticates, so a token never expires mid-request.
_TOKEN_EXPIRY_SKEW_SECONDS = 60


def _jwt_expiry(token: str | None) -> float | None:
    """Best-effort parse of a JWT's ``exp`` claim (epoch seconds)."""
    if not token:
        return None
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        return float(exp) if exp is not None else None
    except Exception:
        return None


class GraphQLModule:
    """Encapsulates GraphQL module configuration, schema, and auth.

    Auth is configured per module (under ``graphql_modules.<module_name>``),
    not on the client: a module authenticates with an AWS API Gateway
    ``x_api_key``, or with a silvaengine_gateway JWT Bearer token.
    """

    def __init__(
        self,
        endpoint_id: str,
        module_name: str | None = None,
        class_name: str | None = None,
        endpoint: str | None = None,
        x_api_key: str | None = None,
        gateway_base_url: str | None = None,
        token_username: str | None = None,
        token_password: str | None = None,
        gateway_token: str | None = None,
    ):
        self.endpoint_id = endpoint_id
        self._module_name = module_name
        self._class_name = class_name
        self._endpoint = endpoint.format(endpoint_id=endpoint_id) if endpoint else None
        self._x_api_key = x_api_key
        self._gateway_base_url = gateway_base_url
        self._token_username = token_username
        self._token_password = token_password
        self._gateway_token = gateway_token
        self._gateway_token_exp = _jwt_expiry(self._gateway_token)
        self._schema = None

    @property
    def module_name(self) -> str | None:
        return self._module_name

    @property
    def class_name(self) -> str | None:
        return self._class_name

    @property
    def endpoint(self) -> str | None:
        return self._endpoint

    @property
    def x_api_key(self) -> str | None:
        return self._x_api_key

    @property
    def gateway_base_url(self) -> str | None:
        return self._gateway_base_url

    @property
    def auth_mode(self) -> str:
        """``"jwt"``, ``"api_key"``, or ``"none"`` for this module."""
        if self._gateway_token or (self._token_username and self._token_password):
            return "jwt"
        if self._x_api_key:
            return "api_key"
        return "none"

    @property
    def schema(self):
        """Get the cached GraphQL schema, loading it if necessary."""
        if self._schema is None and self._module_name and self._class_name:
            self.refresh_schema()
        return self._schema

    def refresh_schema(self):
        """Load or reload the GraphQL schema from the configured module and class."""
        if self._module_name and self._class_name:
            self._schema = Graphql.get_graphql_schema(
                module_name=self._module_name,
                class_name=self._class_name,
            )

    def _token_expired(self) -> bool:
        """True when the cached JWT is at/near its ``exp`` (within the skew)."""
        if self._gateway_token_exp is None:
            return False
        return time.time() >= (self._gateway_token_exp - _TOKEN_EXPIRY_SKEW_SECONDS)

    def get_gateway_token(self) -> str | None:
        """Obtain (or reuse) this module's JWT Bearer token for the gateway."""
        if self._gateway_token and not self._token_expired():
            return self._gateway_token
        if not (self._token_username and self._token_password):
            return self._gateway_token
        if not self._gateway_base_url:
            return self._gateway_token

        resp = httpx.post(
            f"{self._gateway_base_url.rstrip('/')}/auth/token",
            data={
                "username": self._token_username,
                "password": self._token_password,
            },
            timeout=15,
        )
        resp.raise_for_status()
        self._gateway_token = resp.json()["access_token"]
        self._gateway_token_exp = _jwt_expiry(self._gateway_token)
        return self._gateway_token

    def invalidate_gateway_token(self) -> None:
        """Drop the cached JWT so the next call re-authenticates (reactive 401)."""
        self._gateway_token = None
        self._gateway_token_exp = None


class GraphQLClient:
    """Client for executing GraphQL operations via HTTP/2."""

    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]):
        self.logger = logger
        self.setting = setting
        # ``setting`` may arrive freshly persisted via mcp_daemon_engine's
        # loadMcpConfiguration, which stores it through the JSONCamelCase
        # GraphQL scalar — every nested key (including this dict's own
        # per-backend keys like "harness_engineering_engine" and their
        # "token_username"/"class_name" fields) comes back camelCased. A
        # directly-constructed setting dict (e.g. in tests) is already
        # snake_case, so decamelizing here is a no-op for that path.
        if isinstance(self.setting.get("graphql_modules"), dict):
            self.setting["graphql_modules"] = humps.decamelize(
                self.setting["graphql_modules"]
            )
        self._endpoint_id = None
        self._part_id = None
        self._graphql_modules: Dict[str, GraphQLModule] = {}

    @property
    def endpoint_id(self) -> str | None:
        return self._endpoint_id

    @endpoint_id.setter
    def endpoint_id(self, value: str):
        self._endpoint_id = value

    @property
    def part_id(self) -> str | None:
        return self._part_id

    @part_id.setter
    def part_id(self, value: str):
        self._part_id = value

    @property
    def graphql_modules(self) -> Dict[str, GraphQLModule]:
        return self._graphql_modules

    def get_graphql_module(self, module_name: str) -> GraphQLModule | None:
        """Get a GraphQL module by name, lazy-creating it on first access."""
        if not self._graphql_modules.get(module_name):
            module_setting = (
                self.setting.get("graphql_modules", {}).get(module_name, {}) or {}
            )
            self._graphql_modules[module_name] = GraphQLModule(
                endpoint_id=self.endpoint_id,
                module_name=module_name,
                class_name=module_setting.get("class_name"),
                endpoint=module_setting.get("endpoint"),
                x_api_key=module_setting.get("x_api_key"),
                gateway_base_url=module_setting.get("gateway_base_url"),
                token_username=module_setting.get("token_username"),
                token_password=module_setting.get("token_password"),
                gateway_token=module_setting.get("gateway_token"),
            )
        return self._graphql_modules.get(module_name)

    def get_gateway_token(self, module_name: str = "harness_engineering_engine") -> str | None:
        """Obtain the JWT Bearer token for ``module_name``."""
        return self.get_graphql_module(module_name).get_gateway_token()

    def execute_query(
        self,
        function_name: str,
        operation_name: str,
        operation_type: str,
        variables: Dict[str, Any],
        query: str = None,
        module_name: str = "harness_engineering_engine",
        timeout_seconds: float = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query or mutation.

        ``timeout_seconds`` overrides the default 60s timeout for operations
        that may legitimately take longer (e.g. ``runCommand`` mutations that
        trigger a git-refresh on the backend before executing the command).
        When None, falls back to ``command_timeout_seconds`` from the module
        setting for mutations, or 60s for queries.
        """
        try:
            graphql_module = self.get_graphql_module(module_name)
            if query is None:
                query = Graphql.generate_graphql_operation(
                    operation_name, operation_type, graphql_module.schema
                )

            payload = Serializer.json_dumps({"query": query, "variables": variables})

            def _build_headers(token: str | None) -> Dict[str, str]:
                if token:
                    hdrs = {
                        "Authorization": f"Bearer {token}",
                        "Part-Id": self.part_id,
                        "Content-Type": "application/json",
                    }
                else:
                    hdrs = {
                        "x-api-key": graphql_module.x_api_key,
                        "Part-Id": self.part_id,
                        "Content-Type": "application/json",
                    }
                return {k: v for k, v in hdrs.items() if v is not None}

            token = graphql_module.get_gateway_token()

            # Determine the timeout: explicit override > mutation default >
            # 60s base. The mutation default is configurable via the module
            # setting ``command_timeout_seconds`` (default 120s) to give
            # runCommand enough budget for a git-refresh + command execution.
            if timeout_seconds is not None:
                effective_timeout = timeout_seconds
            elif operation_type == "Mutation":
                module_setting = (
                    self.setting.get("graphql_modules", {})
                    .get(module_name, {})
                )
                effective_timeout = float(
                    module_setting.get("command_timeout_seconds", 120.0)
                )
            else:
                effective_timeout = 60.0

            timeout = httpx.Timeout(effective_timeout, connect=15.0)
            with httpx.Client(http2=True, timeout=timeout) as client:
                response = client.post(
                    graphql_module.endpoint,
                    headers=_build_headers(token),
                    content=payload,
                )

                if response.status_code in (401, 403) and (
                    graphql_module.auth_mode == "jwt"
                ):
                    graphql_module.invalidate_gateway_token()
                    token = graphql_module.get_gateway_token()
                    response = client.post(
                        graphql_module.endpoint,
                        headers=_build_headers(token),
                        content=payload,
                    )

            result = response.json()

            if "errors" in result:
                error_message = result["errors"][0].get("message", "GraphQL error")
                raise Exception(f"GraphQL error: {error_message}")

            return result.get("data", {}).get(operation_name)

        except GraphQLError as e:
            self.logger.error(traceback.format_exc())
            return build_error_response(e.message, e.error_code, e.details)
        except Exception as e:
            self.logger.error(traceback.format_exc())
            return build_error_response(
                extract_error_message(str(e)),
                ErrorCode.GRAPHQL_QUERY_FAILED,
            )
