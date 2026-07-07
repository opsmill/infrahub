from dataclasses import dataclass, field

import pytest
from git.exc import GitCommandError

from infrahub.exceptions import (
    RepositoryConnectionError,
    RepositoryCredentialsError,
    RepositoryError,
)
from infrahub.git.base import InfrahubRepositoryBase


@dataclass
class EnrichmentCase:
    name: str
    stderr: str
    expected: type[RepositoryError]
    command: list[str] = field(default_factory=lambda: ["git", "fetch"])


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
        stderr="remote: Repository not found.\nfatal: repository 'https://gitlab.example.com/net/repo.git/' not found",
        expected=RepositoryConnectionError,
    ),
    EnrichmentCase(
        name="authentication_failed",
        stderr="fatal: Authentication failed for 'https://gitlab.example.com/net/repo.git/'",
        expected=RepositoryCredentialsError,
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
            error=error, name="net-repo", location="https://gitlab.example.com/net/repo.git"
        )

    # The generic fallthrough must not swallow a case that should have matched a more specific rule.
    assert type(exc_info.value) is case.expected
