# ruff: noqa: S101, INP001
from __future__ import annotations

import importlib.util
import io
import json
import subprocess  # noqa: S404
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[1] / "repo-context.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("repo_context", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["repo_context"] = module
    spec.loader.exec_module(module)
    return module


rc = load_module()


def run(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)  # noqa: S603, S607


def write(root: Path, path: str, text: str = "x\n") -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    remote = tmp_path / "remote.git"
    root = tmp_path / "work"
    run("init", "--bare", "-b", "stable", str(remote), cwd=tmp_path)
    run("init", "-b", "stable", str(root), cwd=tmp_path)
    run("config", "user.email", "test@example.com", cwd=root)
    run("config", "user.name", "Test", cwd=root)
    write(root, "README.md")
    write(root, ".agents/rules/code-doc-style.md", "# Code documentation style\n")
    write(root, ".agents/rules/frontend.md", '---\npaths:\n  - "frontend/app/src/**/*.tsx"\n---\n\n# Frontend\n')
    run("add", ".", cwd=root)
    run("commit", "-m", "base", cwd=root)
    run("remote", "add", "origin", str(remote), cwd=root)
    run("push", "origin", "stable", cwd=root)
    run("checkout", "-b", "feature", cwd=root)
    write(root, "frontend/app/src/page.tsx")
    write(root, "changelog/+page.added.md")
    run("add", ".", cwd=root)
    run("commit", "-m", "feature", cwd=root)
    write(root, "backend/infrahub/local_only.py")
    write(root, ".agents/skills/copied/SKILL.md")
    monkeypatch.chdir(root)
    monkeypatch.setattr(rc.tempfile, "gettempdir", lambda: str(tmp_path))
    return root


@pytest.mark.usefixtures("repo")
def test_change_includes_uncommitted_files_by_default() -> None:
    change = rc.changed_files("stable", include_uncommitted=True, excludes=[])

    assert change.files == [
        ".agents/skills/copied/SKILL.md",
        "backend/infrahub/local_only.py",
        "changelog/+page.added.md",
        "frontend/app/src/page.tsx",
    ]
    assert change.uncommitted_only == [".agents/skills/copied/SKILL.md", "backend/infrahub/local_only.py"]


@pytest.mark.usefixtures("repo")
def test_committed_option_leaves_uncommitted_files_out_but_still_lists_them() -> None:
    change = rc.changed_files("stable", include_uncommitted=False, excludes=[])

    assert change.files == ["changelog/+page.added.md", "frontend/app/src/page.tsx"]
    assert change.uncommitted_only == [".agents/skills/copied/SKILL.md", "backend/infrahub/local_only.py"]


@pytest.mark.usefixtures("repo")
def test_exclude_glob_removes_matching_paths() -> None:
    change = rc.changed_files("stable", include_uncommitted=True, excludes=[".agents/**", "backend/**"])

    assert change.files == ["changelog/+page.added.md", "frontend/app/src/page.tsx"]
    assert change.excluded == [".agents/skills/copied/SKILL.md", "backend/infrahub/local_only.py"]


@pytest.mark.usefixtures("repo")
def test_rule_without_paths_matches_source_files_only() -> None:
    rules = {rule.path: rule.matched for rule in rc.load_rules([".agents/skills/copied/SKILL.md", "README.md"])}

    assert rules == {}


@pytest.mark.usefixtures("repo")
def test_rule_without_paths_names_the_first_source_file() -> None:
    rules = {
        rule.path: rule.matched for rule in rc.load_rules(["changelog/+page.added.md", "frontend/app/src/page.tsx"])
    }

    assert rules == {
        ".agents/rules/code-doc-style.md": {"(no paths: applies to every source file)": "frontend/app/src/page.tsx"},
        ".agents/rules/frontend.md": {"frontend/app/src/**/*.tsx": "frontend/app/src/page.tsx"},
    }


@pytest.mark.parametrize(
    ("path", "area"),
    [
        ("dev/knowledge/frontend/branches.md", "dev-docs"),
        ("dev/specs/ifc-1/tasks.md", "dev-docs"),
        ("changelog/+page.added.md", "changelog"),
        ("frontend/app/src/page.tsx", "frontend"),
        ("backend/tests/unit/test_x.py", "backend-tests"),
        ("backend/infrahub/core/node.py", "backend"),
        ("docs/docs/index.mdx", "other"),
    ],
)
def test_area_of(path: str, area: str) -> None:
    assert rc.area_of(path) == area


def test_hooks_status_is_active_after_this_checkouts_hook_ran(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session-active")
    rc.hook_marker("test-session-active").write_text(str(repo), encoding="utf-8")

    assert rc.hooks_status() == 0


@pytest.mark.usefixtures("repo")
def test_hooks_status_is_inactive_when_the_hooks_belong_to_another_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session-other")
    rc.hook_marker("test-session-other").write_text(str(tmp_path / "other-checkout"), encoding="utf-8")

    assert rc.hooks_status() == 1


@pytest.mark.usefixtures("repo")
def test_hooks_status_is_inactive_when_no_hook_ran(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session-none")
    rc.hook_marker("test-session-none").unlink(missing_ok=True)

    assert rc.hooks_status() == 1


def test_hook_records_the_project_it_ran_for(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "session_id": "test-session-hook",
        "cwd": str(repo),
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
    }
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({**payload, "tool_input": {"command": "true"}})))

    assert rc.run_hook() == 0
    assert rc.hook_marker("test-session-hook").read_text(encoding="utf-8") == str(repo.resolve())
