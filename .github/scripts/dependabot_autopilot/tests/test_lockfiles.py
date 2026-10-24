from __future__ import annotations

import json

import pytest

from dependabot_autopilot.lockfiles import LockfileError, added_packages

UV_BASE = """\
version = 1
requires-python = ">=3.14"

[[package]]
name = "fastapi"
version = "0.130.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "typing-extensions"
version = "4.14.0"
source = { registry = "https://pypi.org/simple" }
"""

UV_HEAD_VERSION_ONLY = """\
version = 1
requires-python = ">=3.14"

[[package]]
name = "fastapi"
version = "0.131.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "typing-extensions"
version = "4.15.0"
source = { registry = "https://pypi.org/simple" }
"""

UV_HEAD_ADDED = """\
version = 1
requires-python = ">=3.14"

[[package]]
name = "fastapi"
version = "0.131.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "typing_extensions"
version = "4.15.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "Annotated_Doc"
version = "0.0.3"
source = { registry = "https://pypi.org/simple" }
"""

PNPM_BASE = """\
lockfileVersion: '9.0'

importers:
  .:
    dependencies:
      react:
        specifier: ^19.2.0
        version: 19.2.0

packages:

  '@biomejs/biome@2.4.0':
    resolution: {integrity: sha512-aaa}

  react-dom@19.2.0(react@19.2.0):
    resolution: {integrity: sha512-bbb}

  react@19.2.0:
    resolution: {integrity: sha512-ccc}

snapshots:

  react@19.2.0: {}
"""

PNPM_HEAD_VERSION_ONLY = """\
lockfileVersion: '9.0'

packages:

  '@biomejs/biome@2.4.1':
    resolution: {integrity: sha512-aaa}

  react-dom@19.2.1(react@19.2.1):
    resolution: {integrity: sha512-bbb}

  react@19.2.1:
    resolution: {integrity: sha512-ccc}

snapshots:

  react@19.2.1: {}
"""

PNPM_HEAD_ADDED = """\
lockfileVersion: '9.0'

packages:

  '@biomejs/biome@2.4.1':
    resolution: {integrity: sha512-aaa}

  '@biomejs/cli-darwin-arm64@2.4.1':
    resolution: {integrity: sha512-ddd}

  react-dom@19.2.1(react@19.2.1):
    resolution: {integrity: sha512-bbb}

  react@19.2.1:
    resolution: {integrity: sha512-ccc}

  scheduler@0.27.0:
    resolution: {integrity: sha512-eee}

snapshots:

  left-pad@1.3.0: {}
"""


def package_lock(*, packages: dict[str, str]) -> str:
    entries: dict[str, object] = {"": {"name": "docs", "version": "0.0.0"}}
    entries.update({key: {"version": version} for key, version in packages.items()})
    return json.dumps({"name": "docs", "lockfileVersion": 3, "requires": True, "packages": entries})


NPM_BASE = package_lock(
    packages={
        "node_modules/@docusaurus/core": "3.9.0",
        "node_modules/react": "19.2.0",
        "node_modules/@docusaurus/core/node_modules/semver": "7.7.2",
    }
)
NPM_HEAD_VERSION_ONLY = package_lock(
    packages={
        "node_modules/@docusaurus/core": "3.9.1",
        "node_modules/react": "19.2.1",
        "node_modules/@docusaurus/core/node_modules/semver": "7.7.3",
    }
)
NPM_HEAD_ADDED = package_lock(
    packages={
        "node_modules/@docusaurus/core": "3.9.1",
        "node_modules/react": "19.2.1",
        "node_modules/@docusaurus/core/node_modules/semver": "7.7.3",
        "node_modules/@docusaurus/core/node_modules/@types/estree": "1.0.8",
        "node_modules/react/node_modules/loose-envify": "1.4.0",
    }
)


@pytest.mark.parametrize(
    ("path", "base_text", "head_text"),
    [
        pytest.param("uv.lock", UV_BASE, UV_HEAD_VERSION_ONLY, id="uv"),
        pytest.param("python_testcontainers/uv.lock", UV_BASE, UV_HEAD_VERSION_ONLY, id="nested-uv"),
        pytest.param("frontend/pnpm-lock.yaml", PNPM_BASE, PNPM_HEAD_VERSION_ONLY, id="pnpm"),
        pytest.param("docs/package-lock.json", NPM_BASE, NPM_HEAD_VERSION_ONLY, id="npm"),
    ],
)
def test_version_only_changes_add_nothing(path: str, base_text: str, head_text: str) -> None:
    assert added_packages(path=path, base_text=base_text, head_text=head_text) == ()


def test_uv_returns_new_names_normalized() -> None:
    assert added_packages(path="uv.lock", base_text=UV_BASE, head_text=UV_HEAD_ADDED) == ("annotated-doc",)


def test_pnpm_returns_new_scoped_and_unscoped_names_from_packages_only() -> None:
    assert added_packages(path="frontend/pnpm-lock.yaml", base_text=PNPM_BASE, head_text=PNPM_HEAD_ADDED) == (
        "@biomejs/cli-darwin-arm64",
        "scheduler",
    )


def test_npm_returns_new_nested_names() -> None:
    assert added_packages(path="docs/package-lock.json", base_text=NPM_BASE, head_text=NPM_HEAD_ADDED) == (
        "@types/estree",
        "loose-envify",
    )


def test_package_removed_at_head_is_not_added() -> None:
    assert added_packages(path="uv.lock", base_text=UV_HEAD_ADDED, head_text=UV_BASE) == ()


def test_new_lockfile_adds_every_package() -> None:
    assert added_packages(path="frontend/pnpm-lock.yaml", base_text=None, head_text=PNPM_BASE) == (
        "@biomejs/biome",
        "react",
        "react-dom",
    )


def test_deleted_lockfile_adds_nothing() -> None:
    assert added_packages(path="uv.lock", base_text=UV_BASE, head_text=None) == ()


@pytest.mark.parametrize("path", ["pyproject.toml", "frontend/package.json", "yarn.lock", "uv.lock.bak"])
def test_unknown_lockfile_paths_are_ignored(path: str) -> None:
    assert added_packages(path=path, base_text="garbage", head_text="{ not parseable") == ()


@pytest.mark.parametrize(
    ("path", "text"),
    [
        pytest.param("uv.lock", "[[package]\nname =", id="uv"),
        pytest.param("uv.lock", 'package = "not-a-list"', id="uv-shape"),
        pytest.param("uv.lock", "version = 1\n", id="uv-no-packages"),
        pytest.param("uv.lock", '[[package]]\nname = "fastapi"\n', id="uv-no-version"),
        pytest.param("uv.lock", 'version = 2\n[[package]]\nname = "fastapi"\n', id="uv-unsupported-version"),
        pytest.param("frontend/pnpm-lock.yaml", "packages: [unclosed", id="pnpm"),
        pytest.param("frontend/pnpm-lock.yaml", "packages:\n  - listed", id="pnpm-shape"),
        pytest.param("frontend/pnpm-lock.yaml", "- listed", id="pnpm-not-a-mapping"),
        pytest.param("frontend/pnpm-lock.yaml", "lockfileVersion: '9.0'\n", id="pnpm-no-packages"),
        pytest.param("frontend/pnpm-lock.yaml", "packages:\n  react@19.2.0: {}\n", id="pnpm-no-version"),
        pytest.param(
            "frontend/pnpm-lock.yaml",
            "lockfileVersion: '6.0'\npackages:\n  /react@19.2.0: {}\n",
            id="pnpm-unsupported-version",
        ),
        pytest.param("docs/package-lock.json", "{", id="npm"),
        pytest.param("docs/package-lock.json", '{"lockfileVersion": 3, "packages": []}', id="npm-shape"),
        pytest.param("docs/package-lock.json", "[]", id="npm-not-an-object"),
        pytest.param("docs/package-lock.json", '{"lockfileVersion": 3}', id="npm-no-packages"),
        pytest.param("docs/package-lock.json", '{"packages": {}}', id="npm-no-version"),
        pytest.param("docs/package-lock.json", '{"lockfileVersion": 1, "dependencies": {}}', id="npm-v1"),
    ],
)
def test_unparseable_lockfile_raises(path: str, text: str) -> None:
    with pytest.raises(LockfileError, match=path):
        added_packages(path=path, base_text=text, head_text=text)
