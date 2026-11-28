from __future__ import annotations

import subprocess  # noqa: S404
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ENTRYPOINT = Path(__file__).resolve().parents[3] / "development" / "grafana-mcp" / "entrypoint.sh"
EVERY_INTERFACE = "0.0.0.0"  # noqa: S104 - a setting value under test, nothing listens
CALLER_TOKEN = "caller-token-0123456789"
ALLOWED_HOSTS = "localhost:8100,127.0.0.1:8100"
INSTRUCTIONS_TEXT = (
    "In this stack the Grafana MCP server only reads: it has no tool that creates or changes dashboards, "
    "folders, annotations, incidents, alert rules or data sources."
)
SERVER_ARGUMENTS = [
    "--transport",
    "streamable-http",
    "--address",
    f"{EVERY_INTERFACE}:8000",
    "--allowed-hosts",
    ALLOWED_HOSTS,
    "--usage-stats=disabled",
    "--disable-write",
    "--disable-api",
    "--disable-docs",
    "--disable-plugin",
    "--instructions-append",
    INSTRUCTIONS_TEXT,
]
TLS_ARGUMENTS = [
    "--server.tls-cert-file",
    "/etc/grafana-mcp/tls/tls.crt",
    "--server.tls-key-file",
    "/etc/grafana-mcp/tls/tls.key",
]
# The stub stands for the server: it prints what the entrypoint gave it, and the length of the token, not its value.
STUB_SERVER = """#!/bin/sh
for argument in "$@"; do
    echo "argument=$argument"
done
echo "server-token-length=${#MCP_GRAFANA_SERVER_TOKEN}"
echo "do-not-track=$DO_NOT_TRACK"
"""
MISSING_TOKEN = "INFRAHUB_GRAFANA_MCP_TOKEN is not set: set it to the token that AI assistants send"
INCOMPLETE_TLS = "Set both INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE and INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE, or neither"


def _open_address_without_tls(address: str) -> str:
    return (
        f"INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS is {address}, which is open to a network: "
        "set INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE and INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE"
    )


@pytest.fixture
def stub_directory(tmp_path: Path) -> Path:
    stub = tmp_path / "mcp-grafana"
    stub.write_text(STUB_SERVER, encoding="utf-8")
    stub.chmod(0o755)
    return tmp_path


def _run_entrypoint(stub_directory: Path, settings: dict[str, str]) -> subprocess.CompletedProcess[str]:
    environment = {
        "PATH": f"{stub_directory}:/usr/bin:/bin",
        "INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS": ALLOWED_HOSTS,
    } | settings
    return subprocess.run(  # noqa: S603
        ["/bin/sh", str(ENTRYPOINT)], capture_output=True, text=True, check=False, env=environment, timeout=30
    )


def _server_output(arguments: list[str]) -> str:
    lines = [f"argument={argument}" for argument in arguments]
    return "\n".join([*lines, f"server-token-length={len(CALLER_TOKEN)}", "do-not-track=1"]) + "\n"


@dataclass
class RefusalCase:
    name: str
    settings: dict[str, str]
    message: str


@pytest.mark.parametrize(
    "case",
    [
        RefusalCase(name="no_token", settings={}, message=MISSING_TOKEN),
        RefusalCase(name="empty_token", settings={"INFRAHUB_GRAFANA_MCP_TOKEN": ""}, message=MISSING_TOKEN),
        RefusalCase(
            name="no_token_is_reported_before_an_open_address",
            settings={"INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS": EVERY_INTERFACE},
            message=MISSING_TOKEN,
        ),
        RefusalCase(
            name="certificate_without_key",
            settings={"INFRAHUB_GRAFANA_MCP_TOKEN": CALLER_TOKEN, "INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE": "/tls/tls.crt"},
            message=INCOMPLETE_TLS,
        ),
        RefusalCase(
            name="key_without_certificate",
            settings={"INFRAHUB_GRAFANA_MCP_TOKEN": CALLER_TOKEN, "INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE": "/tls/tls.key"},
            message=INCOMPLETE_TLS,
        ),
        RefusalCase(
            name="every_interface_without_tls",
            settings={
                "INFRAHUB_GRAFANA_MCP_TOKEN": CALLER_TOKEN,
                "INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS": EVERY_INTERFACE,
            },
            message=_open_address_without_tls(EVERY_INTERFACE),
        ),
        RefusalCase(
            name="network_address_without_tls",
            settings={"INFRAHUB_GRAFANA_MCP_TOKEN": CALLER_TOKEN, "INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS": "192.0.2.10"},
            message=_open_address_without_tls("192.0.2.10"),
        ),
        RefusalCase(
            name="address_that_only_starts_like_loopback",
            settings={"INFRAHUB_GRAFANA_MCP_TOKEN": CALLER_TOKEN, "INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS": "127.example"},
            message=_open_address_without_tls("127.example"),
        ),
        RefusalCase(
            name="every_ipv6_interface_without_tls",
            settings={"INFRAHUB_GRAFANA_MCP_TOKEN": CALLER_TOKEN, "INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS": "::"},
            message=_open_address_without_tls("::"),
        ),
    ],
    ids=lambda case: case.name,
)
def test_entrypoint_refuses_to_start_the_server(stub_directory: Path, case: RefusalCase) -> None:
    result = _run_entrypoint(stub_directory=stub_directory, settings=case.settings)

    assert result.returncode == 1
    assert result.stderr == f"{case.message}\n"
    assert not result.stdout


@dataclass
class StartCase:
    name: str
    settings: dict[str, str]
    arguments: list[str] = field(default_factory=lambda: list(SERVER_ARGUMENTS))


@pytest.mark.parametrize(
    "case",
    [
        StartCase(name="default_listen_address", settings={}),
        StartCase(name="loopback_address", settings={"INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS": "127.0.0.1"}),
        StartCase(name="other_loopback_address", settings={"INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS": "127.0.0.5"}),
        StartCase(name="ipv6_loopback_address", settings={"INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS": "::1"}),
        StartCase(name="ipv6_loopback_address_in_brackets", settings={"INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS": "[::1]"}),
        StartCase(
            name="loopback_address_with_tls",
            settings={
                "INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE": "/host/tls.crt",
                "INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE": "/host/tls.key",
            },
            arguments=[*SERVER_ARGUMENTS, *TLS_ARGUMENTS],
        ),
        StartCase(
            name="every_interface_with_tls",
            settings={
                "INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS": EVERY_INTERFACE,
                "INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE": "/host/tls.crt",
                "INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE": "/host/tls.key",
            },
            arguments=[*SERVER_ARGUMENTS, *TLS_ARGUMENTS],
        ),
    ],
    ids=lambda case: case.name,
)
def test_entrypoint_starts_the_server(stub_directory: Path, case: StartCase) -> None:
    result = _run_entrypoint(
        stub_directory=stub_directory, settings={"INFRAHUB_GRAFANA_MCP_TOKEN": CALLER_TOKEN} | case.settings
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == _server_output(case.arguments)
    assert not result.stderr
    assert CALLER_TOKEN not in result.stdout


def test_entrypoint_passes_the_allowed_hosts_setting_to_the_server(stub_directory: Path) -> None:
    result = _run_entrypoint(
        stub_directory=stub_directory,
        settings={
            "INFRAHUB_GRAFANA_MCP_TOKEN": CALLER_TOKEN,
            "INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS": "infrahub.example.com:8100",
        },
    )

    assert "argument=--allowed-hosts\nargument=infrahub.example.com:8100\n" in result.stdout
