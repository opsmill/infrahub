import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fast_depends import Provider
from git import Repo
from git.exc import GitCommandError
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.constants import RepositoryInternalStatus, RepositoryOperationalStatus
from infrahub.exceptions import (
    RepositoryConnectionError,
    RepositoryCredentialsError,
    RepositoryError,
    RepositoryInvalidBranchError,
    RepositoryNotFoundError,
    RepositoryPermissionError,
    RepositoryTLSError,
)
from infrahub.git import InfrahubRepository
from infrahub.git.base import InfrahubRepositoryBase, operational_status_for_error
from infrahub.message_bus import InfrahubMessage, Meta
from infrahub.message_bus.messages.git_repository_connectivity import (
    GitRepositoryConnectivity,
    GitRepositoryConnectivityResponse,
    GitRepositoryConnectivityResponseData,
)
from infrahub.message_bus.operations.git.repository import connectivity
from infrahub.workers.dependencies import build_message_bus
from tests.adapters.message_bus import BusRecorder
from tests.helpers.dependency_override import override_dependency
from tests.helpers.test_client import dummy_async_request

TLS_HINT = "SSL verification failed for net-repo, please validate the certificate chain."
CONNECTION_HINT = "Unable to clone the repository net-repo, please check the address and the credential"
TLS_STDERR = (
    "fatal: unable to access 'https://git.example.com/demo.git/': "
    "SSL certificate problem: unable to get local issuer certificate"
)
NOT_FOUND_STDERR = (
    "remote: Repository not found.\nfatal: repository 'https://gitlab.example.com/net/repo.git/' not found"
)


@dataclass
class EnrichmentCase:
    name: str
    stderr: str
    expected: type[RepositoryError]
    command: list[str] = field(default_factory=lambda: ["git", "fetch"])
    is_write_operation: bool = False
    message: str | None = None
    """Enriched message the rule must produce, for cases whose value is the hint rather than the class."""


ENRICHMENT_CASES = [
    EnrichmentCase(
        name="gateway_504",
        stderr="fatal: unable to access 'https://gitlab.example.com/net/repo.git/': The requested URL returned error: 504",
        expected=RepositoryConnectionError,
    ),
    EnrichmentCase(
        name="gateway_502",
        stderr="fatal: unable to access 'https://gitlab.example.com/net/repo.git/': The requested URL returned error: 502",
        expected=RepositoryConnectionError,
    ),
    EnrichmentCase(
        name="rpc_http_504",
        stderr="error: RPC failed; HTTP 504 curl 22 The requested URL returned error: 504\nfatal: expected flush after ref listing",
        expected=RepositoryConnectionError,
    ),
    EnrichmentCase(
        name="could_not_resolve_host",
        stderr="fatal: unable to access 'https://gitlab.example.com/net/repo.git/': Could not resolve host: gitlab.example.com",
        expected=RepositoryConnectionError,
    ),
    EnrichmentCase(
        name="operation_timed_out",
        stderr="fatal: unable to access 'https://gitlab.example.com/repo.git/': Operation timed out after 30001 milliseconds with 0 bytes received",
        expected=RepositoryConnectionError,
    ),
    EnrichmentCase(
        name="couldnt_connect_to_server",
        stderr="fatal: unable to access 'https://gitlab.example.com/repo.git/': "
        "Failed to connect to gitlab.example.com port 443 after 5 ms: Couldn't connect to server",
        expected=RepositoryConnectionError,
    ),
    EnrichmentCase(
        name="repository_not_found",
        stderr=NOT_FOUND_STDERR,
        expected=RepositoryNotFoundError,
        message=CONNECTION_HINT,
    ),
    EnrichmentCase(
        name="local_path_that_is_not_a_repository",
        stderr="fatal: '/srv/git/net-repo' does not appear to be a git repository\n"
        "fatal: Could not read from remote repository.",
        expected=RepositoryConnectionError,
    ),
    EnrichmentCase(
        # GitPython's own text when its kill_after_timeout stops a fetch or a push.
        name="fetch_killed_after_its_timeout",
        stderr="error: process killed because it timed out. kill_after_timeout=60 seconds",
        expected=RepositoryConnectionError,
        message=CONNECTION_HINT,
    ),
    EnrichmentCase(
        # GitPython's text for a local command stopped at its timeout, which says nothing about the remote.
        name="local_command_timeout_is_not_a_connection_error",
        stderr='Timeout: the command "git reset --hard abc" did not complete in 120 secs.',
        expected=RepositoryError,
        command=["git", "reset", "--hard", "abc"],
    ),
    # One case per wording libcurl emits for an unverifiable certificate: the test host's own git covers
    # only the wording of the TLS backend it happens to be linked against, so they are asserted as text.
    EnrichmentCase(
        # OpenSSL handshake path, every curl version.
        name="tls_untrusted_openssl",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': "
        "SSL certificate problem: unable to get local issuer certificate",
        expected=RepositoryTLSError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # OpenSSL verification path up to curl 8.14.
        name="tls_untrusted_openssl_verify_result",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': "
        "SSL certificate verify result: unable to get local issuer certificate (20)",
        expected=RepositoryTLSError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # OpenSSL verification path from curl 8.15, which is what a Homebrew git emits.
        name="tls_untrusted_openssl_verify_result_since_815",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': "
        "SSL certificate OpenSSL verify result: unable to get local issuer certificate (20)",
        expected=RepositoryTLSError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        name="tls_untrusted_gnutls_legacy",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': "
        "server certificate verification failed. CAfile: none CRLfile: none",
        expected=RepositoryTLSError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # GnuTLS from curl 8.10 to 8.14, which is what the shipped image's git emits.
        name="tls_untrusted_gnutls_shipped_image",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': server verification failed: "
        "certificate signer not trusted. (CAfile: /opt/infrahub/tls/ca-bundle.pem CRLfile: none)",
        expected=RepositoryTLSError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # GnuTLS from curl 8.15.
        name="tls_untrusted_gnutls_since_815",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': "
        "SSL certificate verification failed: certificate signer not trusted. "
        "(CAfile: /opt/infrahub/tls/ca-bundle.pem CRLfile: none)",
        expected=RepositoryTLSError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # A certificate issued for another host, OpenSSL wording.
        name="tls_hostname_mismatch_openssl",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': SSL: no alternative certificate "
        "subject name matches target host name 'git.example.com'",
        expected=RepositoryTLSError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # The same failure, GnuTLS wording.
        name="tls_hostname_mismatch_gnutls",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': SSL: certificate subject name "
        "(git.internal) does not match target hostname 'git.example.com'",
        expected=RepositoryTLSError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        name="authentication_failed",
        stderr="fatal: Authentication failed for 'https://gitlab.example.com/net/repo.git/'",
        expected=RepositoryCredentialsError,
    ),
    EnrichmentCase(
        name="permission_write_access_not_granted",
        stderr="ERROR: Write access to repository not granted.\nfatal: The remote end hung up unexpectedly",
        expected=RepositoryPermissionError,
        command=["git", "push", "--dry-run", "--porcelain", "--delete"],
        is_write_operation=True,
    ),
    EnrichmentCase(
        name="permission_denied_to_user",
        stderr="remote: Permission to opsmill/repo.git denied to baduser.\n"
        "fatal: unable to access 'https://github.com/opsmill/repo.git/'",
        expected=RepositoryPermissionError,
        command=["git", "push", "--dry-run", "--porcelain", "--delete"],
        is_write_operation=True,
    ),
    EnrichmentCase(
        name="permission_http_403",
        stderr="fatal: unable to access 'https://github.com/opsmill/repo.git/': The requested URL returned error: 403",
        expected=RepositoryPermissionError,
        command=["git", "push", "--dry-run", "--porcelain", "--delete"],
        is_write_operation=True,
    ),
    EnrichmentCase(
        name="permission_gitlab_not_allowed",
        stderr="remote: You are not allowed to push code to this project.\nfatal: unable to access ...",
        expected=RepositoryPermissionError,
        command=["git", "push", "--dry-run", "--porcelain", "--delete"],
        is_write_operation=True,
    ),
    EnrichmentCase(
        name="permission_gitlab_not_allowed_upload",
        stderr="remote: You are not allowed to upload code.\nfatal: unable to access ...",
        expected=RepositoryPermissionError,
        command=["git", "push", "--dry-run", "--porcelain", "--delete"],
        is_write_operation=True,
    ),
    EnrichmentCase(
        name="permission_gitea_denied_writing",
        stderr="remote: Gitea: User permission denied for writing.\nfatal: unable to access ...",
        expected=RepositoryPermissionError,
        command=["git", "push", "--dry-run", "--porcelain", "--delete"],
        is_write_operation=True,
    ),
    EnrichmentCase(
        name="read_403_not_classified_as_permission",
        stderr="fatal: unable to access 'https://github.com/opsmill/repo.git/': The requested URL returned error: 403",
        expected=RepositoryError,
    ),
    EnrichmentCase(
        name="pull_with_unmerged_files",
        stderr="error: Pulling is not possible because you have unmerged files.\n"
        "fatal: Exiting because of an unresolved conflict.",
        expected=RepositoryError,
        command=["git", "pull", "-v", "--", "origin", "branch01"],
        message="Unable to pull repository net-repo, there are conflicts that must be resolved.",
    ),
    EnrichmentCase(
        name="unclassified_error_falls_through",
        stderr="fatal: something entirely unexpected happened",
        expected=RepositoryError,
    ),
]


@pytest.mark.parametrize("case", ENRICHMENT_CASES, ids=lambda c: c.name)
def test_raise_enriched_error_static_classification(case: EnrichmentCase) -> None:
    error = GitCommandError(command=case.command, status=128, stderr=case.stderr)

    with pytest.raises(case.expected) as exc_info:
        InfrahubRepositoryBase._raise_enriched_error_static(
            error=error,
            name="net-repo",
            location="https://gitlab.example.com/net/repo.git",
            is_write_operation=case.is_write_operation,
        )

    # The generic fallthrough must not swallow a case that should have matched a more specific rule.
    assert type(exc_info.value) is case.expected
    if case.message is not None:
        assert exc_info.value.message == case.message


@dataclass
class StatusCase:
    name: str
    error: RepositoryError
    expected: RepositoryOperationalStatus


STATUS_CASES = [
    StatusCase(
        name="connection",
        error=RepositoryConnectionError(identifier="net-repo"),
        expected=RepositoryOperationalStatus.ERROR_CONNECTION,
    ),
    StatusCase(
        name="certificate_not_accepted",
        error=RepositoryTLSError(identifier="net-repo"),
        expected=RepositoryOperationalStatus.ERROR_CONNECTION,
    ),
    StatusCase(
        name="repository_not_found",
        error=RepositoryNotFoundError(identifier="net-repo"),
        expected=RepositoryOperationalStatus.ERROR_CONNECTION,
    ),
    StatusCase(
        name="credentials",
        error=RepositoryCredentialsError(identifier="net-repo"),
        expected=RepositoryOperationalStatus.ERROR_CRED,
    ),
    StatusCase(
        name="write_permission",
        error=RepositoryPermissionError(identifier="net-repo"),
        expected=RepositoryOperationalStatus.ERROR_CRED,
    ),
    StatusCase(
        name="invalid_branch",
        error=RepositoryInvalidBranchError(identifier="net-repo", branch_name="main", location="/srv/git/net-repo"),
        expected=RepositoryOperationalStatus.ERROR,
    ),
    StatusCase(
        name="unclassified",
        error=RepositoryError(identifier="net-repo"),
        expected=RepositoryOperationalStatus.ERROR,
    ),
]


@pytest.mark.parametrize("case", STATUS_CASES, ids=lambda c: c.name)
def test_operational_status_for_a_repository_error(case: StatusCase) -> None:
    assert operational_status_for_error(error=case.error) == case.expected


def failing_remote_location(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stderr: str) -> str:
    """Return a remote location whose Git transport prints ``stderr`` and fails.

    Git runs ``git-remote-<transport>`` for a ``<transport>::<address>`` location and passes its stderr
    through, as it does for the HTTPS helper whose messages a real remote failure produces.
    """
    helper_directory = tmp_path / "remote-helper"
    helper_directory.mkdir()
    helper = helper_directory / "git-remote-failing"
    helper.write_text(f"#!/bin/sh\ncat >&2 <<'EOF'\n{stderr}\nEOF\nexit 128\n", encoding="utf-8")
    helper.chmod(0o755)
    monkeypatch.setenv("PATH", f"{helper_directory}{os.pathsep}{os.environ['PATH']}")
    # Allow the helper's transport whatever protocol policy the host's Git configuration sets.
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "failing")
    return "failing::https://git.example.com/net/repo.git"


class StatusRecordingClient(InfrahubClient):
    """An SDK client that records the status of every operational status update instead of sending it."""

    def __init__(self) -> None:
        super().__init__(config=Config(requester=dummy_async_request))
        self.recorded_statuses: list[str] = []

    async def execute_graphql(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.recorded_statuses.append(kwargs["variables"]["status"])
        return {}


async def test_fetch_refused_for_its_certificate_records_the_connection_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config.SETTINGS.git, "repositories_directory", str(tmp_path / "repositories"))
    location = failing_remote_location(tmp_path=tmp_path, monkeypatch=monkeypatch, stderr=TLS_STDERR)
    repository = InfrahubRepository(
        id=UUID(str(UUIDT.new())),
        name="net-repo",
        location=location,
        default_branch="main",
        has_origin=True,
        internal_status=RepositoryInternalStatus.ACTIVE,
        infrahub_branch_name="main",
    )
    Repo.init(repository.directory_default).create_remote(name="origin", url=location, allow_unsafe_protocols=True)
    recorder = StatusRecordingClient()
    repository.client = recorder

    with pytest.raises(RepositoryTLSError, match=rf"^{TLS_HINT}$"):
        await repository.fetch()

    assert recorder.recorded_statuses == [RepositoryOperationalStatus.ERROR_CONNECTION.value]


class ReplyRecordingBus(BusRecorder):
    """Message bus double that keeps every reply instead of sending it."""

    def __init__(self) -> None:
        super().__init__()
        self.replies: list[InfrahubMessage] = []

    async def reply(self, message: InfrahubMessage, routing_key: str) -> None:
        self.replies.append(message)


@dataclass
class ConnectivityCase:
    name: str
    stderr: str
    message: str


@pytest.mark.parametrize(
    "case",
    [
        ConnectivityCase(name="certificate_not_accepted", stderr=TLS_STDERR, message=TLS_HINT),
        ConnectivityCase(name="repository_not_found", stderr=NOT_FOUND_STDERR, message=CONNECTION_HINT),
    ],
    ids=lambda c: c.name,
)
async def test_connectivity_check_reports_the_connection_status_for_a_connection_subtype(
    case: ConnectivityCase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dependency_provider: Provider
) -> None:
    location = failing_remote_location(tmp_path=tmp_path, monkeypatch=monkeypatch, stderr=case.stderr)
    message = GitRepositoryConnectivity(
        repository_name="net-repo", repository_location=location, meta=Meta(reply_to="connectivity-check")
    )
    bus = ReplyRecordingBus()

    with override_dependency(build_message_bus, lambda: bus, dependency_provider=dependency_provider):
        await connectivity.fn(message=message)

    [reply] = bus.replies
    assert isinstance(reply, GitRepositoryConnectivityResponse)
    assert reply.data == GitRepositoryConnectivityResponseData(
        message=case.message,
        success=False,
        operational_status=RepositoryOperationalStatus.ERROR_CONNECTION.value,
    )
