import os
from pathlib import Path

import pytest


@pytest.fixture
def git_sources_dir(tmp_path: Path) -> Path:
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    return source_dir


@pytest.fixture(autouse=True)
def git_identity() -> None:
    """Ensure git author/committer identity is set for environments without global git config (e.g. CI)."""
    defaults = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@test.com",
    }
    for var, value in defaults.items():
        if var not in os.environ:
            os.environ[var] = value
