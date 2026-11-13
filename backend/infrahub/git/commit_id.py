import re

COMMIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def readable_commit(commit: str | None) -> str | None:
    """Return a commit the graph records, or None when the value is empty or not a full commit id."""
    return commit if commit and COMMIT_SHA_PATTERN.fullmatch(commit) else None
