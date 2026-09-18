from __future__ import annotations

import hashlib
import os
import ssl
import tempfile
from pathlib import Path

PEM_MARKER = "-----BEGIN "

# CA bundles supplied inline as PEM text are written here so that git, boto3, the Neo4j driver and
# redis-py, which only accept a file, can read them. Honours TMPDIR like every other temporary file.
MATERIALIZED_BUNDLE_DIRECTORY = Path(tempfile.gettempdir()) / "infrahub-tls"


def is_pem_text(value: str) -> bool:
    """Whether a CA setting holds PEM content rather than the path of a file."""
    return PEM_MARKER in value


def normalize_pem_text(value: str) -> str:
    """Return PEM text in the form written to disk: surrounding whitespace dropped, one trailing newline.

    A value without any line break but with literal ``\\n`` sequences is expanded: environment files and
    shells cannot always carry real line breaks, and a PEM certificate on a single line is invalid anyway,
    so the escaped form is the only reading that can work.
    """
    text = value.strip()
    if "\n" not in text and "\\n" in text:
        text = text.replace("\\n", "\n")
    return text + "\n"


def validate_pem_text(pem: str) -> None:
    """Check that PEM text parses as a certificate bundle.

    Raises:
        ValueError: When the text holds no loadable certificate.

    """
    try:
        ssl.create_default_context().load_verify_locations(cadata=pem)
    except ssl.SSLError as exc:
        raise ValueError(f"the value is not a valid PEM certificate bundle: {exc}") from exc


def validate_ca_file(path: Path) -> None:
    """Check that a path points at an existing, readable PEM certificate bundle.

    Raises:
        ValueError: When the path is not an existing file, cannot be read, or does not hold certificates.

    """
    try:
        is_file = path.is_file()
    except OSError:
        # Raised when the value is far too long to be a path.
        is_file = False
    if not is_file:
        raise ValueError(f"must be the path to an existing file or PEM text, got {str(path)!r}")
    try:
        ssl.create_default_context(cafile=str(path))
    except (OSError, ssl.SSLError) as exc:
        raise ValueError(f"unable to load the CA bundle from {path}: {exc}") from exc


def materialize_pem_text(pem: str, directory: Path | None = None) -> Path:
    """Write PEM text to a file named after its content and return the path.

    The name derives from a hash of the content, so every process handed the same bundle converges on the
    same file without coordination, and a changed bundle lands in a new file instead of being rewritten
    under a reader. The write goes through a temporary file and an atomic rename.

    Raises:
        ValueError: When the directory or the file cannot be written.

    """
    directory = directory or MATERIALIZED_BUNDLE_DIRECTORY
    digest = hashlib.sha256(pem.encode("utf-8")).hexdigest()[:32]
    target = directory / f"ca-bundle-{digest}.pem"
    try:
        if target.is_file() and target.read_text(encoding="utf-8") == pem:
            return target
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / f".{target.name}.{os.getpid()}.tmp"
        temporary.write_text(pem, encoding="utf-8")
        Path(temporary).replace(target)
    except OSError as exc:
        raise ValueError(f"unable to write the CA bundle under {directory}: {exc}") from exc
    return target


def resolve_ca_bundle(value: str, directory: Path | None = None) -> str:
    """Return the path of a readable PEM file for a CA setting given as a file path or as PEM text.

    PEM text is validated and written to ``directory`` (the materialized bundle directory by default);
    a path must point at an existing, loadable bundle and is returned unchanged.

    Raises:
        ValueError: When the path does not exist or cannot be loaded, the text is not a PEM bundle, or
            the text cannot be written to disk.

    """
    if is_pem_text(value):
        pem = normalize_pem_text(value)
        validate_pem_text(pem)
        return str(materialize_pem_text(pem, directory=directory))
    path = Path(value)
    validate_ca_file(path)
    return str(path)
