from dataclasses import dataclass, field

import pytest
from git.exc import GitCommandError

from infrahub.exceptions import (
    RepositoryConnectionError,
    RepositoryCredentialsError,
    RepositoryError,
)
from infrahub.git.base import InfrahubRepositoryBase

TLS_HINT = "SSL verification failed for net-repo, please validate the certificate chain."


@dataclass
class EnrichmentCase:
    name: str
    stderr: str
    expected: type[RepositoryError]
    command: list[str] = field(default_factory=lambda: ["git", "fetch"])
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
        stderr="remote: Repository not found.\nfatal: repository 'https://gitlab.example.com/net/repo.git/' not found",
        expected=RepositoryConnectionError,
    ),
    # One case per wording libcurl emits for an unverifiable certificate: the test host's own git covers
    # only the wording of the TLS backend it happens to be linked against, so they are asserted as text.
    EnrichmentCase(
        # OpenSSL handshake path, every curl version.
        name="tls_untrusted_openssl",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': "
        "SSL certificate problem: unable to get local issuer certificate",
        expected=RepositoryConnectionError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # OpenSSL verification path up to curl 8.14.
        name="tls_untrusted_openssl_verify_result",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': "
        "SSL certificate verify result: unable to get local issuer certificate (20)",
        expected=RepositoryConnectionError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # OpenSSL verification path from curl 8.15, which is what a Homebrew git emits.
        name="tls_untrusted_openssl_verify_result_since_815",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': "
        "SSL certificate OpenSSL verify result: unable to get local issuer certificate (20)",
        expected=RepositoryConnectionError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        name="tls_untrusted_gnutls_legacy",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': "
        "server certificate verification failed. CAfile: none CRLfile: none",
        expected=RepositoryConnectionError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # GnuTLS from curl 8.10 to 8.14, which is what the shipped image's git emits.
        name="tls_untrusted_gnutls_shipped_image",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': server verification failed: "
        "certificate signer not trusted. (CAfile: /opt/infrahub/tls/ca-bundle.pem CRLfile: none)",
        expected=RepositoryConnectionError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # GnuTLS from curl 8.15.
        name="tls_untrusted_gnutls_since_815",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': "
        "SSL certificate verification failed: certificate signer not trusted. "
        "(CAfile: /opt/infrahub/tls/ca-bundle.pem CRLfile: none)",
        expected=RepositoryConnectionError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # A certificate issued for another host, OpenSSL wording.
        name="tls_hostname_mismatch_openssl",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': SSL: no alternative certificate "
        "subject name matches target host name 'git.example.com'",
        expected=RepositoryConnectionError,
        message=TLS_HINT,
    ),
    EnrichmentCase(
        # The same failure, GnuTLS wording.
        name="tls_hostname_mismatch_gnutls",
        stderr="fatal: unable to access 'https://git.example.com/demo.git/': SSL: certificate subject name "
        "(git.internal) does not match target hostname 'git.example.com'",
        expected=RepositoryConnectionError,
        message=TLS_HINT,
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
    if case.message is not None:
        assert exc_info.value.message == case.message
