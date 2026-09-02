from __future__ import annotations

import asyncio
import datetime
import ipaddress
import ssl
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from git import Actor, Git, Repo
from git.exc import GitCommandError

from infrahub.config import GitSettings
from infrahub.git.global_config import (
    GIT_HTTP_SSL_CA_INFO,
    GIT_HTTP_SSL_VERIFY,
    apply_git_tls_config,
    set_git_global_setting,
    unset_git_global_setting,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
CA_BUNDLE = str(TEST_DATA_DIR / "ca-bundle.pem")


@pytest.fixture
def git_global_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point git at a throwaway global config so the tests never touch the real one."""
    config_file = tmp_path / "gitconfig"
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config_file))
    # Environment overrides would bypass the global config the code under test writes.
    for variable in ("GIT_SSL_CAINFO", "GIT_SSL_NO_VERIFY", "GIT_SSL_CAPATH"):
        monkeypatch.delenv(variable, raising=False)
    return config_file


async def read_global_setting(name: str) -> str | None:
    proc = await asyncio.create_subprocess_exec(
        "git", "config", "--global", "--get", name, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    return stdout.decode().strip()


class TestGitGlobalSettings:
    async def test_set_writes_the_key(self, git_global_config: Path) -> None:
        await set_git_global_setting("user.name", "Infrahub Test")

        assert await read_global_setting("user.name") == "Infrahub Test"

    async def test_unset_removes_the_key(self, git_global_config: Path) -> None:
        await set_git_global_setting("user.name", "Infrahub Test")
        await unset_git_global_setting("user.name")

        assert await read_global_setting("user.name") is None

    async def test_unset_of_an_absent_key_is_not_an_error(self, git_global_config: Path) -> None:
        await unset_git_global_setting("user.name")

        assert await read_global_setting("user.name") is None


class TestApplyGitTlsConfig:
    async def test_ca_file_is_written_as_ssl_ca_info(self, git_global_config: Path) -> None:
        await apply_git_tls_config(settings=GitSettings(tls_ca_file=CA_BUNDLE))

        assert await read_global_setting(GIT_HTTP_SSL_CA_INFO) == CA_BUNDLE
        assert await read_global_setting(GIT_HTTP_SSL_VERIFY) is None

    async def test_insecure_disables_ssl_verify(self, git_global_config: Path) -> None:
        await apply_git_tls_config(settings=GitSettings(tls_insecure=True))

        assert await read_global_setting(GIT_HTTP_SSL_VERIFY) == "false"
        assert await read_global_setting(GIT_HTTP_SSL_CA_INFO) is None

    async def test_defaults_write_nothing(self, git_global_config: Path) -> None:
        await apply_git_tls_config(settings=GitSettings())

        assert await read_global_setting(GIT_HTTP_SSL_CA_INFO) is None
        assert await read_global_setting(GIT_HTTP_SSL_VERIFY) is None

    async def test_removed_settings_are_cleared_from_a_persisted_config(self, git_global_config: Path) -> None:
        await apply_git_tls_config(settings=GitSettings(tls_ca_file=CA_BUNDLE))
        await apply_git_tls_config(settings=GitSettings(tls_insecure=True))
        assert await read_global_setting(GIT_HTTP_SSL_CA_INFO) is None
        assert await read_global_setting(GIT_HTTP_SSL_VERIFY) == "false"

        await apply_git_tls_config(settings=GitSettings())

        assert await read_global_setting(GIT_HTTP_SSL_CA_INFO) is None
        assert await read_global_setting(GIT_HTTP_SSL_VERIFY) is None


# --- End to end: git really trusts the configured bundle ------------------------------------------------


def _write_pem(path: Path, *objects: bytes) -> Path:
    path.write_bytes(b"".join(objects))
    return path


def _issue_test_pki(directory: Path) -> tuple[Path, Path, Path]:
    """Create a throwaway CA and a server certificate for localhost signed by it.

    Returns the paths of the CA certificate, the server certificate and the server private key.
    """
    now = datetime.datetime.now(tz=datetime.UTC)
    validity = datetime.timedelta(days=1)

    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Infrahub Test Private CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + validity)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    server_key = ec.generate_private_key(ec.SECP256R1())
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(ca_name)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + validity)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]
            ),
            critical=False,
        )
        .add_extension(x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    ca_path = _write_pem(directory / "private-ca.pem", ca_cert.public_bytes(serialization.Encoding.PEM))
    server_cert_path = _write_pem(directory / "server.pem", server_cert.public_bytes(serialization.Encoding.PEM))
    server_key_path = _write_pem(
        directory / "server.key",
        server_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ),
    )
    return ca_path, server_cert_path, server_key_path


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _git_supports_https() -> bool:
    exec_path = Git().execute(["git", "--exec-path"])
    return (Path(str(exec_path).strip()) / "git-remote-https").exists()


@pytest.fixture
def https_git_server(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    """Serve a bare repository over HTTPS with a certificate issued by a private CA.

    Yields the clone URL and the path of the private CA certificate. The dumb HTTP transport is
    enough for a clone and needs nothing beyond ``git update-server-info`` and a static file server.
    """
    if not _git_supports_https():
        pytest.skip("git on this host has no HTTPS remote helper")

    ca_path, server_cert_path, server_key_path = _issue_test_pki(tmp_path)

    source = Repo.init(tmp_path / "source", initial_branch="main")
    (tmp_path / "source" / "README.md").write_text("private CA test\n", encoding="utf-8")
    source.index.add(["README.md"])
    author = Actor("Test", "test@example.com")
    source.index.commit("initial commit", author=author, committer=author)

    web_root = tmp_path / "www"
    web_root.mkdir()
    bare = Repo.clone_from(str(tmp_path / "source"), str(web_root / "repo.git"), bare=True)
    bare.git.update_server_info()

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=str(server_cert_path), keyfile=str(server_key_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(web_root)))
    server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"https://localhost:{server.server_address[1]}/repo.git", ca_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestGitTrustsTheConfiguredBundle:
    async def test_private_ca_is_rejected_without_configuration(
        self, git_global_config: Path, https_git_server: tuple[str, Path], tmp_path: Path
    ) -> None:
        url, _ = https_git_server
        await apply_git_tls_config(settings=GitSettings())

        with pytest.raises(GitCommandError) as exc_info:
            Repo.clone_from(url, str(tmp_path / "clone"))

        # OpenSSL- and GnuTLS-linked git builds word the failure differently; the product's error
        # enrichment in infrahub.git.base matches the same two phrases.
        stderr = str(exc_info.value.stderr)
        assert "SSL certificate problem" in stderr or "server certificate verification failed" in stderr

    async def test_clone_succeeds_with_the_configured_ca_file(
        self, git_global_config: Path, https_git_server: tuple[str, Path], tmp_path: Path
    ) -> None:
        url, ca_path = https_git_server
        await apply_git_tls_config(settings=GitSettings(tls_ca_file=str(ca_path)))

        clone = Repo.clone_from(url, str(tmp_path / "clone"))

        assert (Path(clone.working_dir) / "README.md").read_text(encoding="utf-8") == "private CA test\n"

    async def test_clone_succeeds_when_verification_is_disabled(
        self, git_global_config: Path, https_git_server: tuple[str, Path], tmp_path: Path
    ) -> None:
        url, _ = https_git_server
        await apply_git_tls_config(settings=GitSettings(tls_insecure=True))

        clone = Repo.clone_from(url, str(tmp_path / "clone"))

        assert (Path(clone.working_dir) / "README.md").exists()
