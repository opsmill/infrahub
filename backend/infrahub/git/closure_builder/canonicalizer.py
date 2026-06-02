from __future__ import annotations


def canonicalize_path(path: str) -> str:
    """Return the canonical repo-relative form of a path entering a transform's dependency closure.

    Properties enforced:

    - POSIX forward-slash separator (backslashes are converted).
    - Leading ``/`` is stripped; a leading slash is interpreted as the repository
      root, matching the ``.gitignore`` convention.
    - Leading ``./`` segments are stripped.
    - Trailing ``/`` is stripped.
    - Symlinks are not resolved; the canonical form is what git sees.
    - Case is preserved.
    - Idempotent: ``canonicalize_path(canonicalize_path(p)) == canonicalize_path(p)``.

    Empty strings and inputs that collapse to the repository root are rejected because
    they do not name a dependency and would silently match every entry in a diff.

    Raises:
        ValueError: If ``path`` is empty or collapses to the repository root.

    """
    if not path:
        raise ValueError("Path must not be empty")

    normalized = path.replace("\\", "/")

    while True:
        previous = normalized
        normalized = normalized.lstrip("/")
        normalized = normalized.removeprefix("./")
        normalized = normalized.rstrip("/")
        if normalized == previous:
            break

    if normalized in ("", "."):
        raise ValueError(f"Path resolves to the repository root and is not a valid dependency: {path!r}")

    return normalized
