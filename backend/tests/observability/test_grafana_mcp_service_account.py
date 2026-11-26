"""Run the service account script against real Grafana servers.

The script reads Grafana's JSON answers with ``sed`` and ``grep``, so only a real
server shows whether it still understands them. The cases run on the Grafana
version of the Compose stack and on the one of the Helm chart. The script runs
inside the Grafana container, with the tools of the image that the stack uses for it.

Requires a Docker daemon, and network access the first time, to pull the images.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from tests.helpers.constants import INFRAHUB_USE_TEST_CONTAINERS

if TYPE_CHECKING:
    from collections.abc import Generator

SCRIPT_DIRECTORY = Path(__file__).resolve().parents[3] / "development" / "grafana-mcp"
SCRIPT_IN_CONTAINER = "/scripts/create-service-account.sh"
TOKEN_FILE = "/tmp/grafana-mcp/token"  # noqa: S108 - a path inside the Grafana container, not on the host
ACCOUNT_NAME = "infrahub-grafana-mcp"
ADMIN_USER = "admin"
ADMIN_PASSWORD = "observability-test-admin"
GRAFANA_PORT = 3000
GRAFANA_START_TIMEOUT_SECONDS = 120
REQUEST_TIMEOUT_SECONDS = 30
LOGIN_REFUSED = "Grafana refused the admin login: set INFRAHUB_GRAFANA_ADMIN_USER and INFRAHUB_GRAFANA_ADMIN_PASSWORD"


@dataclass
class ScriptResult:
    exit_code: int
    output: str


class Grafana:
    def __init__(self, container: DockerContainer) -> None:
        self._container = container
        self._admin = httpx.Client(
            base_url=f"http://{container.get_container_host_ip()}:{container.get_exposed_port(GRAFANA_PORT)}",
            auth=(ADMIN_USER, ADMIN_PASSWORD),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    def close(self) -> None:
        self._admin.close()

    def run_script(self, admin_password: str = ADMIN_PASSWORD, grafana_url: str | None = None) -> ScriptResult:
        result = self._container.get_wrapped_container().exec_run(
            ["/bin/sh", SCRIPT_IN_CONTAINER],
            environment={
                "GRAFANA_URL": grafana_url or f"http://localhost:{GRAFANA_PORT}",
                "GRAFANA_ADMIN_USER": ADMIN_USER,
                "GRAFANA_ADMIN_PASSWORD": admin_password,
                "GRAFANA_MCP_TOKEN_FILE": TOKEN_FILE,
                "GRAFANA_WAIT_SECONDS": "4",
            },
        )
        return ScriptResult(exit_code=result.exit_code, output=result.output.decode())

    def read_token(self) -> str:
        result = self._container.get_wrapped_container().exec_run(["cat", TOKEN_FILE])
        assert result.exit_code == 0
        return result.output.decode()

    def token_file_mode(self) -> str:
        result = self._container.get_wrapped_container().exec_run(["stat", "-c", "%a", TOKEN_FILE])
        return result.output.decode().strip()

    def remove_token_file(self) -> None:
        self._container.get_wrapped_container().exec_run(["rm", "-f", TOKEN_FILE])

    def write_token_file(self, content: str) -> None:
        self._container.get_wrapped_container().exec_run(["/bin/sh", "-c", f"printf '%s' '{content}' > {TOKEN_FILE}"])

    def accounts(self) -> list[dict[str, Any]]:
        response = self._admin.get("/api/serviceaccounts/search", params={"query": ACCOUNT_NAME})
        response.raise_for_status()
        return response.json()["serviceAccounts"]

    def account_summary(self) -> list[tuple[str, str, int]]:
        return [(account["name"], account["role"], account["tokens"]) for account in self.accounts()]

    def token_names(self) -> list[str]:
        [account] = [account for account in self.accounts() if account["name"] == ACCOUNT_NAME]
        response = self._admin.get(f"/api/serviceaccounts/{account['id']}/tokens")
        response.raise_for_status()
        return [token["name"] for token in response.json()]

    def create_account(self, name: str, role: str) -> None:
        self._admin.post("/api/serviceaccounts", json={"name": name, "role": role}).raise_for_status()

    def set_role(self, role: str) -> None:
        [account] = [account for account in self.accounts() if account["name"] == ACCOUNT_NAME]
        self._admin.patch(f"/api/serviceaccounts/{account['id']}", json={"role": role}).raise_for_status()

    def delete_accounts(self) -> None:
        for account in self.accounts():
            self._admin.delete(f"/api/serviceaccounts/{account['id']}").raise_for_status()

    def status_with_token(self, token: str) -> int:
        with httpx.Client(base_url=self._admin.base_url, timeout=REQUEST_TIMEOUT_SECONDS) as client:
            return client.get("/api/user", headers={"Authorization": f"Bearer {token}"}).status_code


@pytest.fixture(scope="module", params=["11.1.5", "11.4.0"])
def grafana_container(request: pytest.FixtureRequest) -> Generator[DockerContainer, None, None]:
    if not INFRAHUB_USE_TEST_CONTAINERS:
        pytest.skip("Needs a Grafana container, and test containers are turned off")
    container = (
        DockerContainer(image=f"grafana/grafana:{request.param}")
        .with_env("GF_SECURITY_ADMIN_USER", ADMIN_USER)
        .with_env("GF_SECURITY_ADMIN_PASSWORD", ADMIN_PASSWORD)
        .with_exposed_ports(GRAFANA_PORT)
        .with_volume_mapping(str(SCRIPT_DIRECTORY), "/scripts", "ro")
    )
    with container:
        wait_for_logs(container, "HTTP Server Listen", timeout=GRAFANA_START_TIMEOUT_SECONDS)
        yield container


@pytest.fixture
def grafana(grafana_container: DockerContainer) -> Generator[Grafana, None, None]:
    server = Grafana(container=grafana_container)
    server.delete_accounts()
    server.remove_token_file()
    yield server
    server.close()


def test_first_run_creates_a_viewer_account_with_one_working_token(grafana: Grafana) -> None:
    result = grafana.run_script()

    token = grafana.read_token()
    assert result.exit_code == 0, result.output
    assert grafana.account_summary() == [(ACCOUNT_NAME, "Viewer", 1)]
    assert grafana.token_names() == [ACCOUNT_NAME]
    assert grafana.status_with_token(token) == httpx.codes.OK
    assert grafana.token_file_mode() == "400"
    assert token not in result.output


def test_second_run_keeps_the_token_that_still_works(grafana: Grafana) -> None:
    grafana.run_script()
    first_token = grafana.read_token()

    result = grafana.run_script()

    assert result.exit_code == 0, result.output
    assert grafana.read_token() == first_token
    assert grafana.account_summary() == [(ACCOUNT_NAME, "Viewer", 1)]
    assert grafana.status_with_token(first_token) == httpx.codes.OK
    assert first_token not in result.output


@dataclass
class LostTokenCase:
    name: str
    file_content: str | None


@pytest.mark.parametrize(
    "case",
    [
        LostTokenCase(name="missing_file", file_content=None),
        LostTokenCase(name="empty_file", file_content=""),
        LostTokenCase(name="token_that_grafana_does_not_know", file_content="glsa_unknown"),
    ],
    ids=lambda case: case.name,
)
def test_run_replaces_a_token_that_does_not_work(grafana: Grafana, case: LostTokenCase) -> None:
    grafana.run_script()
    first_token = grafana.read_token()
    grafana.remove_token_file()
    if case.file_content is not None:
        grafana.write_token_file(case.file_content)

    result = grafana.run_script()

    new_token = grafana.read_token()
    assert result.exit_code == 0, result.output
    assert new_token != first_token
    assert grafana.account_summary() == [(ACCOUNT_NAME, "Viewer", 1)]
    assert grafana.token_names() == [ACCOUNT_NAME]
    assert grafana.status_with_token(new_token) == httpx.codes.OK
    assert grafana.status_with_token(first_token) == httpx.codes.UNAUTHORIZED
    assert new_token not in result.output


@pytest.mark.parametrize("has_working_token", [False, True], ids=["without_token", "with_working_token"])
def test_run_gives_the_viewer_role_to_an_account_that_had_another_role(
    grafana: Grafana, has_working_token: bool
) -> None:
    grafana.create_account(name=ACCOUNT_NAME, role="Editor")
    if has_working_token:
        grafana.run_script()
        grafana.set_role("Editor")
        assert grafana.account_summary() == [(ACCOUNT_NAME, "Editor", 1)]

    result = grafana.run_script()

    assert result.exit_code == 0, result.output
    assert grafana.account_summary() == [(ACCOUNT_NAME, "Viewer", 1)]
    assert grafana.status_with_token(grafana.read_token()) == httpx.codes.OK


def test_run_leaves_an_account_with_a_longer_name_alone(grafana: Grafana) -> None:
    grafana.create_account(name=f"{ACCOUNT_NAME}-of-the-operator", role="Editor")

    result = grafana.run_script()

    assert result.exit_code == 0, result.output
    assert sorted(grafana.account_summary()) == [
        (ACCOUNT_NAME, "Viewer", 1),
        (f"{ACCOUNT_NAME}-of-the-operator", "Editor", 0),
    ]


def test_wrong_admin_password_names_the_two_settings(grafana: Grafana) -> None:
    result = grafana.run_script(admin_password="not-the-admin-password")

    assert result.exit_code == 1
    assert result.output == f"{LOGIN_REFUSED}\n"
    assert grafana.accounts() == []


def test_unreachable_grafana_names_the_address(grafana: Grafana) -> None:
    result = grafana.run_script(grafana_url="http://localhost:3999")

    assert result.exit_code == 1
    assert result.output == "Grafana did not answer at http://localhost:3999 within 4 seconds\n"
