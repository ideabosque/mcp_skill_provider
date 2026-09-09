#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Live HTTP smoke test for a selected Harness skill via mcp_skill_provider.

This script expects a running SilvaEngine gateway. It authenticates with the
gateway, optionally reloads the mcp_skill_provider configuration, retrieves the
selected skill metadata, and executes a selected argv through the gateway MCP
HTTP route backed by mcp_daemon_engine.

Example:
    python mcp_skill_provider/tests/test_selected_skill_mcp_http.py \
        --skill ingredient-research \
        --argv-json '["ioa","research","summary","--ingredient","Vitamin C"]' \
        --reload-mcp --expect-stdout

    python mcp_skill_provider/tests/test_selected_skill_mcp_http.py \
        --skill ingredient-research \
        --argv ioa research summary --ingredient "Vitamin C" \
        --http-trace --expect-stdout
"""
from __future__ import annotations

__author__ = "bibow"

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_GATEWAY_ENV = (
    Path(__file__).resolve().parents[3]
    / "silvaengine_gateway"
    / "silvaengine_gateway"
    / "tests"
    / ".env"
)


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _request_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    form_body: Optional[Dict[str, str]] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    body: Optional[bytes] = None
    request_headers = dict(headers or {})

    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    elif form_body is not None:
        body = urlencode(form_body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    req = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {payload}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not connect to {url}: {exc}") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {url}: {payload[:1000]}") from exc


def _auth_token(base_url: str, username: str, password: str) -> str:
    data = _request_json(
        "POST",
        f"{base_url.rstrip('/')}/auth/token",
        form_body={"username": username, "password": password},
        timeout=30,
    )
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Gateway auth response did not include access_token.")
    return str(token)


def _graphql(
    base_url: str,
    endpoint_id: str,
    path: str,
    token: str,
    part_id: str,
    query: str,
    variables: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = _request_json(
        "POST",
        f"{base_url.rstrip('/')}/{endpoint_id}/{path}",
        headers={"Authorization": f"Bearer {token}", "Part-Id": part_id},
        json_body={"query": query, "variables": variables or {}},
        timeout=120,
    )
    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors from {path}: {json.dumps(data['errors'])}")
    return data.get("data", {})


def _mcp_call(
    base_url: str,
    endpoint_id: str,
    token: str,
    part_id: str,
    tool_name: str,
    arguments: Dict[str, Any],
    request_id: int,
    *,
    http_trace: bool = False,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{endpoint_id}/mcp"
    json_body = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    if http_trace:
        print(f"\n=== MCP HTTP request: {tool_name} ===")
        print(f"POST {url}")
        print(json.dumps(json_body, indent=2, ensure_ascii=False))

    data = _request_json(
        "POST",
        url,
        headers={"Authorization": f"Bearer {token}", "Part-Id": part_id},
        json_body=json_body,
        timeout=120,
    )
    if http_trace:
        print(f"\n=== MCP HTTP response: {tool_name} ===")
        print(json.dumps(data, indent=2, ensure_ascii=False))

    if data.get("error"):
        error_data = data["error"].get("data", "")
        if "No module named 'mcp_skill_provider'" in str(error_data):
            raise RuntimeError(
                "The live gateway process cannot import mcp_skill_provider. "
                "Install this package into the Python environment that runs "
                "the gateway, for example: "
                "C:\\Python312\\env\\Scripts\\python.exe -m pip install -e ."
            )
        raise RuntimeError(f"MCP error from {tool_name}: {json.dumps(data['error'])}")
    return data


def _content_text(response: Dict[str, Any]) -> str:
    content = response.get("result", {}).get("content", [])
    if not content:
        raise RuntimeError(f"MCP response has no content: {json.dumps(response)}")
    text = content[0].get("text")
    if text is None:
        raise RuntimeError(f"MCP content has no text: {json.dumps(content[0])}")
    return str(text)


def _parse_tool_json(response: Dict[str, Any]) -> Dict[str, Any]:
    text = _content_text(response)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Tool response text is not JSON: {text[:1000]}") from exc
    if parsed.get("error"):
        raise RuntimeError(json.dumps(parsed, indent=2))
    return parsed


def _print_json_section(title: str, payload: Dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _print_mcp_http_transport(base_url: str, endpoint_id: str) -> None:
    print("MCP HTTP transport:")
    print(f"  daemon: mcp_daemon_engine")
    print(f"  endpoint: POST {base_url.rstrip('/')}/{endpoint_id}/mcp")
    print("  jsonrpc method: tools/call")


def _load_mcp_configuration(
    base_url: str,
    endpoint_id: str,
    token: str,
    part_id: str,
    username: str,
    password: str,
) -> Dict[str, Any]:
    query = """
mutation Load($variables: JSONCamelCase) {
  loadMcpConfiguration(
    moduleName: "mcp_skill_provider"
    updatedBy: "selected_skill_smoke_test"
    variables: $variables
  ) {
    ok
    message
    stats { tools resources prompts modules settings }
  }
}
"""
    variables = {
        "graphql_modules": {
            "harness_engineering_engine": {
                "class_name": "HarnessEngineeringEngine",
                "endpoint": f"{base_url.rstrip('/')}/{{endpoint_id}}/harness_graphql",
                "x_api_key": "",
                "gateway_base_url": base_url.rstrip("/"),
                "token_username": username,
                "token_password": password,
                "command_timeout_seconds": 120,
            }
        }
    }
    data = _graphql(
        base_url,
        endpoint_id,
        "mcp_daemon_graphql",
        token,
        part_id,
        query,
        {"variables": variables},
    )
    result = data.get("loadMcpConfiguration", {})
    if not result.get("ok"):
        raise RuntimeError(f"loadMcpConfiguration failed: {result.get('message')}")
    return result


def _argv_from_args(args: argparse.Namespace) -> List[str]:
    if args.argv_json:
        argv_json = args.argv_json.strip()
        if (
            len(argv_json) >= 2
            and argv_json[0] == argv_json[-1]
            and argv_json[0] in {"'", '"'}
        ):
            argv_json = argv_json[1:-1]
        parsed = json.loads(argv_json)
        if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
            raise ValueError("--argv-json must be a JSON array of strings.")
        return parsed

    if args.argv:
        return args.argv

    raise ValueError("Provide --argv-json or pass argv tokens after --argv.")


def _extract_argv_tokens(raw_args: List[str]) -> tuple[List[str], Optional[List[str]]]:
    """Extract --argv command tokens while allowing script flags after them."""
    if "--argv" not in raw_args:
        return raw_args, None

    known_flags = {
        "--reload-mcp",
        "--expect-stdout",
        "--summary-only",
        "--print-stdout",
        "--http-trace",
    }
    known_options = {
        "--base-url",
        "--endpoint-id",
        "--part-id",
        "--env-file",
        "--username",
        "--password",
        "--skill",
        "--argv-json",
        "--max-stdout",
    }

    index = raw_args.index("--argv")
    parser_args = raw_args[:index]
    command_argv: List[str] = []
    i = index + 1

    while i < len(raw_args):
        token = raw_args[i]
        if token in known_flags:
            parser_args.append(token)
            i += 1
            continue
        if token in known_options:
            parser_args.append(token)
            if i + 1 >= len(raw_args):
                raise ValueError(f"{token} requires a value.")
            parser_args.append(raw_args[i + 1])
            i += 2
            continue
        command_argv.append(token)
        i += 1

    return parser_args, command_argv


def main(argv: Optional[List[str]] = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    parser_args, extracted_argv = _extract_argv_tokens(raw_args)

    parser = argparse.ArgumentParser(
        description="Run a selected skill through mcp_skill_provider over a live gateway."
    )
    parser.add_argument("--base-url", default=os.getenv("GATEWAY_BASE_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--endpoint-id", default=os.getenv("ENDPOINT_ID", "gpt"))
    parser.add_argument("--part-id", default=os.getenv("PART_ID", "nestaging"))
    parser.add_argument("--env-file", type=Path, default=DEFAULT_GATEWAY_ENV)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--skill", required=True)
    parser.add_argument(
        "--argv-json",
        help='Command argv as JSON, e.g. ["ioa","research","summary","--ingredient","Vitamin C"]',
    )
    parser.add_argument(
        "--argv",
        nargs=argparse.REMAINDER,
        help="Command argv tokens.",
    )
    parser.add_argument("--reload-mcp", action="store_true")
    parser.add_argument("--expect-stdout", action="store_true")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print only compact status lines instead of full get_skill/run_command JSON.",
    )
    parser.add_argument(
        "--print-stdout",
        action="store_true",
        help="Deprecated; stdout is included in the full run_command JSON by default.",
    )
    parser.add_argument(
        "--http-trace",
        action="store_true",
        help=(
            "Print the MCP-over-HTTP JSON-RPC request and response envelopes. "
            "Authorization headers are never printed."
        ),
    )
    parser.add_argument("--max-stdout", type=int, default=2000)

    args = parser.parse_args(parser_args)
    if extracted_argv is not None:
        args.argv = extracted_argv
    _load_env_file(args.env_file)

    username = args.username or os.getenv("ADMIN_USERNAME", "admin")
    password = args.password or os.getenv("ADMIN_PASSWORD", "admin123")
    command_argv = _argv_from_args(args)

    token = _auth_token(args.base_url, username, password)
    _print_mcp_http_transport(args.base_url, args.endpoint_id)

    if args.reload_mcp:
        loaded = _load_mcp_configuration(
            args.base_url,
            args.endpoint_id,
            token,
            args.part_id,
            username,
            password,
        )
        print(f"loadMcpConfiguration: ok=true stats={loaded.get('stats')}")

    skill_response = _mcp_call(
        args.base_url,
        args.endpoint_id,
        token,
        args.part_id,
        "get_skill",
        {"name": args.skill},
        1,
        http_trace=args.http_trace,
    )
    skill = _parse_tool_json(skill_response)
    allowed = skill.get("allowed_commands") or []
    cli_packages = skill.get("cli_packages") or []
    if args.summary_only:
        print(
            "get_skill: "
            f"name={skill.get('name')} version={skill.get('version')} "
            f"allowed_commands={len(allowed)} cli_packages={len(cli_packages)}"
        )
    else:
        _print_json_section("MCP get_skill result", skill)

    run_response = _mcp_call(
        args.base_url,
        args.endpoint_id,
        token,
        args.part_id,
        "run_command",
        {"name": args.skill, "argv": command_argv},
        2,
        http_trace=args.http_trace,
    )
    run_result = _parse_tool_json(run_response)
    stdout = run_result.get("stdout") or ""
    stderr = run_result.get("stderr") or ""
    if args.summary_only:
        print(
            "run_command: "
            f"exit_code={run_result.get('exit_code')} "
            f"timed_out={run_result.get('timed_out')} "
            f"truncated={run_result.get('truncated')} "
            f"stdout_len={len(stdout)} stderr_len={len(stderr)}"
        )
    else:
        _print_json_section("MCP run_command result", run_result)

    if args.expect_stdout and not stdout:
        raise RuntimeError("Expected stdout, but command returned an empty stdout.")

    if args.print_stdout and args.summary_only and stdout:
        print("\n--- stdout ---")
        print(stdout[: args.max_stdout])
        if len(stdout) > args.max_stdout:
            print(f"\n--- stdout truncated locally at {args.max_stdout} characters ---")

    if stderr:
        print("\n--- stderr ---", file=sys.stderr)
        print(stderr, file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
