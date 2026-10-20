from __future__ import annotations

from pathlib import Path

import pytest

from infrahub.tls.bundle import (
    is_pem_text,
    materialize_pem_text,
    normalize_pem_text,
    resolve_ca_bundle,
    validate_pem_text,
)

TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
CA_BUNDLE = TEST_DATA_DIR / "ca-bundle.pem"


@pytest.fixture
def pem() -> str:
    return CA_BUNDLE.read_text(encoding="utf-8")


class TestPemDetection:
    def test_pem_text_is_detected(self, pem: str) -> None:
        assert is_pem_text(pem) is True

    def test_path_is_not_pem_text(self) -> None:
        assert is_pem_text(str(CA_BUNDLE)) is False
        assert is_pem_text("/etc/ssl/certs/does-not-exist.pem") is False


class TestNormalizePemText:
    def test_strips_and_terminates_with_one_newline(self, pem: str) -> None:
        assert normalize_pem_text("\n  " + pem + "\n\n") == pem.strip() + "\n"

    def test_expands_escaped_newlines_only_when_no_real_ones_exist(self, pem: str) -> None:
        escaped = pem.strip().replace("\n", "\\n")

        assert normalize_pem_text(escaped) == pem.strip() + "\n"
        # A value that already has line breaks is left alone, even if it also contains the two characters.
        assert normalize_pem_text(pem.strip() + "\\n") == pem.strip() + "\\n\n"


class TestValidatePemText:
    def test_certificate_bundle_is_accepted(self, pem: str) -> None:
        validate_pem_text(normalize_pem_text(pem))

    def test_garbage_between_markers_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="not a valid PEM certificate bundle"):
            validate_pem_text("-----BEGIN CERTIFICATE-----\nnope\n-----END CERTIFICATE-----\n")


class TestMaterializePemText:
    def test_writes_a_file_named_after_the_content(self, tmp_path: Path, pem: str) -> None:
        text = normalize_pem_text(pem)

        path = materialize_pem_text(text, directory=tmp_path / "tls")

        assert path.parent == tmp_path / "tls"
        assert path.name.startswith("ca-bundle-")
        assert path.suffix == ".pem"
        assert path.read_text(encoding="utf-8") == text
        assert [entry.name for entry in path.parent.iterdir()] == [path.name]

    def test_same_content_converges_on_the_same_file(self, tmp_path: Path, pem: str) -> None:
        text = normalize_pem_text(pem)

        first = materialize_pem_text(text, directory=tmp_path)
        first_mtime = first.stat().st_mtime_ns
        second = materialize_pem_text(text, directory=tmp_path)

        assert second == first
        assert second.stat().st_mtime_ns == first_mtime  # not rewritten under a reader

    def test_different_content_gets_a_different_file(self, tmp_path: Path, pem: str) -> None:
        first = materialize_pem_text(normalize_pem_text(pem), directory=tmp_path)
        second = materialize_pem_text(
            normalize_pem_text((TEST_DATA_DIR / "ca-bundle-4096.pem").read_text(encoding="utf-8")), directory=tmp_path
        )

        assert first != second

    def test_unwritable_directory_is_reported(self, tmp_path: Path, pem: str) -> None:
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("occupied", encoding="utf-8")

        with pytest.raises(ValueError, match="unable to write the CA bundle under"):
            materialize_pem_text(normalize_pem_text(pem), directory=blocker)


class TestResolveCaBundle:
    def test_existing_file_is_returned_unchanged(self) -> None:
        assert resolve_ca_bundle(str(CA_BUNDLE)) == str(CA_BUNDLE)

    def test_pem_text_is_materialized(self, tmp_path: Path, pem: str) -> None:
        resolved = Path(resolve_ca_bundle(pem, directory=tmp_path))

        assert resolved.parent == tmp_path
        assert resolved.read_text(encoding="utf-8") == normalize_pem_text(pem)

    def test_missing_path_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="must be the path to an existing file or PEM text"):
            resolve_ca_bundle(str(tmp_path / "missing.pem"))

    def test_file_without_certificates_is_rejected(self, tmp_path: Path) -> None:
        bogus = tmp_path / "bogus.pem"
        bogus.write_text("not a certificate", encoding="utf-8")

        with pytest.raises(ValueError, match="unable to load the CA bundle from"):
            resolve_ca_bundle(str(bogus))
