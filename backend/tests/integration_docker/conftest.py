from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

CURRENT_DIRECTORY = Path(__file__).parent.resolve()

# CI splits this suite across parallel shard jobs selected with `-m shard_<name>`.
# Every test file declares its shard with a module-level `pytestmark`; the shards
# are balanced by measured per-class runtimes, so pick the lighter one for a new
# file (or rebalance) rather than defaulting to a fixed shard.
# Keep this set in sync with the backend-docker-integration `shard:` matrix in
# .github/workflows/ci.yml — a marker without a matrix entry never runs in CI.
_SHARD_MARKERS = {"shard_a", "shard_b"}


def pytest_configure(config: pytest.Config) -> None:
    for marker in sorted(_SHARD_MARKERS):
        config.addinivalue_line("markers", f"{marker}: CI shard for backend/tests/integration_docker")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Guard the shard partition: every test needs exactly one shard marker.

    Registered tryfirst so it runs BEFORE the `-m` filter deselects anything —
    every shard job therefore validates the FULL collection, and a new test
    file without a shard marker fails CI instead of silently never running.

    Raises:
        UsageError: If a test file declares no shard marker or several.

    """
    offenders: dict[str, str] = {}
    for item in items:
        if not Path(str(item.path)).is_relative_to(CURRENT_DIRECTORY):
            continue
        found = _SHARD_MARKERS.intersection(marker.name for marker in item.iter_markers())
        if len(found) != 1:
            reason = "has no shard marker" if not found else f"has multiple shard markers {sorted(found)}"
            offenders[str(item.path)] = reason
    if offenders:
        details = "\n".join(f"  {path}: {reason}" for path, reason in sorted(offenders.items()))
        raise pytest.UsageError(
            "Every integration_docker test file must declare exactly one CI shard via a\n"
            f"module-level `pytestmark = pytest.mark.shard_<name>`:\n{details}"
        )


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
