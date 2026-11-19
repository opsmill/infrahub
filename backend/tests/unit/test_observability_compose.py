from __future__ import annotations

import os
import shutil
import subprocess  # noqa: S404
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

DEVELOPMENT_DIR = Path(__file__).resolve().parents[3] / "development"
TRACING_ENVIRONMENT = {
    # An operator turns tracing off by setting INFRAHUB_TRACE_ENABLE=false next to the Compose file.
    "INFRAHUB_TRACE_ENABLE": "${INFRAHUB_TRACE_ENABLE:-true}",
    "INFRAHUB_TRACE_EXPORTER_TYPE": "otlp",
    "INFRAHUB_TRACE_EXPORTER_PROTOCOL": "grpc",
    "INFRAHUB_TRACE_EXPORTER_ENDPOINT": "http://infrahub-tempo:4317",
    "INFRAHUB_TRACE_SAMPLE_RATIO": "${INFRAHUB_TRACE_SAMPLE_RATIO:-0.1}",
}


def _services(file_name: str) -> dict[str, Any]:
    return yaml.safe_load((DEVELOPMENT_DIR / file_name).read_text(encoding="utf-8"))["services"]


@pytest.mark.parametrize("service", ["infrahub-server", "task-worker"])
def test_standalone_observability_file_turns_tracing_on(service: str) -> None:
    assert _services("docker-compose-observability-standalone.yml")[service] == {"environment": TRACING_ENVIRONMENT}


def test_observability_file_leaves_the_infrahub_services_to_the_stack_that_loads_it() -> None:
    # The development stack loads this file too, and a service without an image makes Compose reject the project.
    assert {"server", "infrahub-server", "task-worker"} & set(_services("docker-compose-observability.yml")) == set()


GRAFANA_MCP_PROFILE = "grafana-mcp"
GRAFANA_MCP_SERVICES = ["infrahub-grafana-mcp", "infrahub-grafana-mcp-init"]
GRAFANA_MCP_COMPOSE_FILES = ["docker-compose-observability.yml", "docker-compose-observability-standalone.yml"]
GRAFANA_MCP_IMAGE = "grafana/mcp-grafana:2.0.2@sha256:78d208116ec52b09b44f0eca66892073b39aefcb64483c54d43255c8eab7e97a"
GRAFANA_MCP_ENTRYPOINT = ["/bin/sh", "/usr/local/bin/grafana-mcp-entrypoint.sh"]
GRAFANA_MCP_INIT_ENTRYPOINT = ["/bin/sh", "/usr/local/bin/create-service-account.sh"]
GRAFANA_MCP_TOKEN_FILE = "/var/run/grafana-mcp/token"
# The server image runs as this user, and the init step gives it the token file.
GRAFANA_MCP_USER = "1000:999"
GRAFANA_MCP_ENVIRONMENT = {
    "INFRAHUB_GRAFANA_MCP_TOKEN": "${INFRAHUB_GRAFANA_MCP_TOKEN:-}",
    "INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS": "${INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS:-localhost:8100,127.0.0.1:8100}",
    "INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS": "${INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS:-127.0.0.1}",
    "INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE": "${INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE:-}",
    "INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE": "${INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE:-}",
    "GRAFANA_URL": "http://infrahub-grafana:3000",
    "GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE": GRAFANA_MCP_TOKEN_FILE,
    "DO_NOT_TRACK": "1",
}
GRAFANA_MCP_INIT_ENVIRONMENT = {
    "GRAFANA_URL": "http://infrahub-grafana:3000",
    "GRAFANA_ADMIN_USER": "${INFRAHUB_GRAFANA_ADMIN_USER:-admin}",
    "GRAFANA_ADMIN_PASSWORD": "${INFRAHUB_GRAFANA_ADMIN_PASSWORD:-admin}",
    "GRAFANA_MCP_TOKEN_FILE": GRAFANA_MCP_TOKEN_FILE,
    "GRAFANA_MCP_TOKEN_FILE_OWNER": GRAFANA_MCP_USER,
}
# A bind mount needs a source on the Docker host even when the operator sets no TLS file.
GRAFANA_MCP_TLS_VOLUMES = [
    {
        "type": "bind",
        "source": "${INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE:-/dev/null}",
        "target": "/etc/grafana-mcp/tls/tls.crt",
        "read_only": True,
    },
    {
        "type": "bind",
        "source": "${INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE:-/dev/null}",
        "target": "/etc/grafana-mcp/tls/tls.key",
        "read_only": True,
    },
]


def _compose(file_name: str) -> dict[str, Any]:
    return yaml.safe_load((DEVELOPMENT_DIR / file_name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("file_name", GRAFANA_MCP_COMPOSE_FILES)
def test_grafana_mcp_services_are_the_only_services_of_their_profile(file_name: str) -> None:
    in_profile = sorted(
        name for name, service in _services(file_name).items() if GRAFANA_MCP_PROFILE in service.get("profiles", [])
    )

    assert in_profile == GRAFANA_MCP_SERVICES


@pytest.mark.parametrize("file_name", GRAFANA_MCP_COMPOSE_FILES)
@pytest.mark.parametrize("service", GRAFANA_MCP_SERVICES)
def test_grafana_mcp_services_start_only_with_their_profile(file_name: str, service: str) -> None:
    assert _services(file_name)[service]["profiles"] == [GRAFANA_MCP_PROFILE]


def test_standalone_file_starts_every_other_service_without_a_profile() -> None:
    services = _services("docker-compose-observability-standalone.yml")

    assert sorted(name for name, service in services.items() if "profiles" in service) == GRAFANA_MCP_SERVICES


@pytest.mark.parametrize("file_name", GRAFANA_MCP_COMPOSE_FILES)
def test_grafana_mcp_server_service(file_name: str) -> None:
    service = _services(file_name)["infrahub-grafana-mcp"]
    # The standalone file embeds the entrypoint as a config, so only the mounts that both files share are compared.
    shared_volumes = [volume for volume in service["volumes"] if not str(volume).startswith("./")]

    assert service["image"] == GRAFANA_MCP_IMAGE
    assert service["user"] == GRAFANA_MCP_USER
    assert service["entrypoint"] == GRAFANA_MCP_ENTRYPOINT
    assert service["environment"] == GRAFANA_MCP_ENVIRONMENT
    assert service["ports"] == ["${INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS:-127.0.0.1}:8100:8000"]
    assert service["depends_on"] == {"infrahub-grafana-mcp-init": {"condition": "service_completed_successfully"}}
    assert shared_volumes == ["grafana_mcp_token:/var/run/grafana-mcp:ro", *GRAFANA_MCP_TLS_VOLUMES]
    # A restart policy would start the server again after it refused to start without a token.
    assert "restart" not in service
    assert "command" not in service


@pytest.mark.parametrize("file_name", GRAFANA_MCP_COMPOSE_FILES)
def test_grafana_mcp_init_service(file_name: str) -> None:
    services = _services(file_name)
    service = services["infrahub-grafana-mcp-init"]
    shared_volumes = [volume for volume in service["volumes"] if not str(volume).startswith("./")]

    # The step reuses the image of the Grafana service, so the stack pulls no other image for it.
    assert service["image"] == services["infrahub-grafana"]["image"]
    assert service["user"] == "root"
    assert service["entrypoint"] == GRAFANA_MCP_INIT_ENTRYPOINT
    assert service["environment"] == GRAFANA_MCP_INIT_ENVIRONMENT
    assert service["depends_on"] == ["infrahub-grafana"]
    assert shared_volumes == ["grafana_mcp_token:/var/run/grafana-mcp"]
    assert "ports" not in service
    assert "restart" not in service


@pytest.mark.parametrize("file_name", GRAFANA_MCP_COMPOSE_FILES)
def test_grafana_mcp_token_volume_is_declared(file_name: str) -> None:
    assert "grafana_mcp_token" in _compose(file_name)["volumes"]


@pytest.mark.parametrize("file_name", GRAFANA_MCP_COMPOSE_FILES)
def test_grafana_admin_account_comes_from_the_settings_that_the_init_step_reads(file_name: str) -> None:
    environment = _services(file_name)["infrahub-grafana"]["environment"]

    assert "GF_SECURITY_ADMIN_USER=${INFRAHUB_GRAFANA_ADMIN_USER:-admin}" in environment
    assert "GF_SECURITY_ADMIN_PASSWORD=${INFRAHUB_GRAFANA_ADMIN_PASSWORD:-admin}" in environment


def test_observability_file_mounts_the_two_scripts() -> None:
    services = _services("docker-compose-observability.yml")

    assert (
        "./grafana-mcp/entrypoint.sh:/usr/local/bin/grafana-mcp-entrypoint.sh:ro"
        in services["infrahub-grafana-mcp"]["volumes"]
    )
    assert (
        "./grafana-mcp/create-service-account.sh:/usr/local/bin/create-service-account.sh:ro"
        in services["infrahub-grafana-mcp-init"]["volumes"]
    )


@dataclass
class EmbeddedScriptCase:
    name: str
    service: str
    script: str
    target: str


@pytest.mark.parametrize(
    "case",
    [
        EmbeddedScriptCase(
            name="entrypoint",
            service="infrahub-grafana-mcp",
            script="entrypoint.sh",
            target="/usr/local/bin/grafana-mcp-entrypoint.sh",
        ),
        EmbeddedScriptCase(
            name="create_service_account",
            service="infrahub-grafana-mcp-init",
            script="create-service-account.sh",
            target="/usr/local/bin/create-service-account.sh",
        ),
    ],
    ids=lambda case: case.name,
)
def test_standalone_file_embeds_the_script_that_the_service_runs(case: EmbeddedScriptCase) -> None:
    compose = _compose("docker-compose-observability-standalone.yml")
    [config] = compose["services"][case.service]["configs"]
    script = (DEVELOPMENT_DIR / "grafana-mcp" / case.script).read_text(encoding="utf-8")

    assert config["target"] == case.target
    # Compose reads "$$" in an embedded file as one "$".
    assert compose["configs"][config["source"]]["content"] == script.replace("$", "$$")


@pytest.mark.skipif(shutil.which("docker") is None, reason="Needs the Docker Compose command to load the file")
def test_standalone_file_loads_with_the_profile_on_and_no_tls_setting(tmp_path: Path) -> None:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith(("INFRAHUB_GRAFANA", "COMPOSE_"))
    }
    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "docker",
            "compose",
            "--project-directory",
            str(tmp_path),
            "--project-name",
            "grafana-mcp-config-check",
            "--file",
            str(DEVELOPMENT_DIR.parent / "docker-compose.yml"),
            "--file",
            str(DEVELOPMENT_DIR / "docker-compose-observability-standalone.yml"),
            "--profile",
            GRAFANA_MCP_PROFILE,
            "config",
            "--services",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert sorted(set(GRAFANA_MCP_SERVICES) & set(result.stdout.split())) == GRAFANA_MCP_SERVICES
