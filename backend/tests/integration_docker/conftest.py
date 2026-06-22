from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(scope="session", autouse=True)
def disable_git_commit_signing(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Commit unsigned in the throwaway git repositories these tests build.

    Repository setup commits with dulwich, which honors the host's ``commit.gpgsign``
    setting and imports the optional ``gpg`` bindings to sign. Those bindings are
    absent on many developer machines (and CI never signs), so signing would fail the
    repository setup with ``ModuleNotFoundError: No module named 'gpg'``. Point git's
    configuration at a minimal identity with signing disabled for the test session.
    """
    config = tmp_path_factory.mktemp("git") / "config"
    config.write_text(
        "[user]\n\tname = Infrahub Test\n\temail = test@infrahub.local\n[commit]\n\tgpgsign = false\n",
        encoding="utf-8",
    )

    overrides = {"GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_SYSTEM": os.devnull}
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
