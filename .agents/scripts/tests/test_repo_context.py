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


def init_repo(tmp_path: Path, name: str, base_files: list[str]) -> Path:
    """Create a checkout whose `stable` holds `base_files`, pushed to its own origin, on branch `feature`."""
    remote = tmp_path / f"{name}.git"
    root = tmp_path / name
    run("init", "--bare", "-b", "stable", str(remote), cwd=tmp_path)
    run("init", "-b", "stable", str(root), cwd=tmp_path)
    run("config", "user.email", "test@example.com", cwd=root)
    run("config", "user.name", "Test", cwd=root)
    for path in base_files:
        write(root, path)
    run("add", ".", cwd=root)
    run("commit", "-m", "base", cwd=root)
    run("remote", "add", "origin", str(remote), cwd=root)
    run("push", "origin", "stable", cwd=root)
    run("checkout", "-b", "feature", cwd=root)
    return root


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    write(tmp_path, "work/.agents/rules/code-doc-style.md", "# Code documentation style\n")
    write(
        tmp_path, "work/.agents/rules/frontend.md", '---\npaths:\n  - "frontend/app/src/**/*.tsx"\n---\n\n# Frontend\n'
    )
    root = init_repo(tmp_path, "work", ["README.md"])
    write(root, "frontend/app/src/page.tsx")
    write(root, "changelog/+page.added.md")
    run("add", ".", cwd=root)
    run("commit", "-m", "feature", cwd=root)
    write(root, "backend/infrahub/local_only.py")
    write(root, ".agents/skills/copied/SKILL.md")
    monkeypatch.chdir(root)
    monkeypatch.setattr(rc, "TOOLING_ROOT", root.resolve())
    monkeypatch.setattr(rc.tempfile, "gettempdir", lambda: str(tmp_path))
    return root


@pytest.mark.usefixtures("repo")
def test_manifest_marks_rules_missing_from_the_reviewed_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = init_repo(tmp_path, "target", [".agents/rules/code-doc-style.md"])
    write(target, "frontend/app/src/other.tsx")

    context = run_manifest(monkeypatch, capsys, "--repo", str(target))

    assert {rule["path"]: rule["on_base"] for rule in context["rules"]} == {
        ".agents/rules/code-doc-style.md": True,
        ".agents/rules/frontend.md": False,
    }


def run_manifest(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *args: str) -> dict:
    monkeypatch.setattr("sys.argv", ["repo-context.py", "--json", "--base", "stable", *args])
    assert rc.main() == 0
    return json.loads(capsys.readouterr().out)


@pytest.mark.usefixtures("repo")
def test_manifest_reviews_another_checkout_with_this_checkouts_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = init_repo(tmp_path, "target", ["README.md"])
    write(target, "frontend/app/src/other.tsx")

    context = run_manifest(monkeypatch, capsys, "--repo", str(target))

    assert context["repo"] == str(target.resolve())
    assert context["files"] == ["frontend/app/src/other.tsx"]
    assert [rule["path"] for rule in context["rules"]] == [
        ".agents/rules/code-doc-style.md",
        ".agents/rules/frontend.md",
    ]


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


def test_change_lists_deleted_files_apart_from_the_files_to_read(repo: Path) -> None:
    run("rm", "-q", "README.md", cwd=repo)
    run("commit", "-m", "delete readme", cwd=repo)
    (repo / "frontend/app/src/page.tsx").unlink()

    change = rc.changed_files("stable", include_uncommitted=True, excludes=[])

    assert change.files == [
        ".agents/skills/copied/SKILL.md",
        "backend/infrahub/local_only.py",
        "changelog/+page.added.md",
    ]
    assert change.deleted == ["README.md", "frontend/app/src/page.tsx"]


def test_change_lists_both_sides_of_an_uncommitted_rename(repo: Path) -> None:
    run("mv", "README.md", "README2.md", cwd=repo)

    change = rc.changed_files("stable", include_uncommitted=True, excludes=[])

    assert "README2.md" in change.files
    assert change.deleted == ["README.md"]
    assert "README.md" not in change.uncommitted_only


def test_change_keeps_a_path_with_a_space_unquoted(repo: Path) -> None:
    write(repo, "frontend/app/src/a b.tsx")

    assert "frontend/app/src/a b.tsx" in rc.changed_files("stable", include_uncommitted=True, excludes=[]).files


def test_manifest_exits_2_when_git_fails(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run("remote", "remove", "origin", cwd=repo)
    monkeypatch.setattr("sys.argv", ["repo-context.py", "--base", "stable"])

    assert rc.main() == rc.EXIT_GIT_FAILED


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
        ("dev/specs/ifc-1/tasks.md", "dev-specs"),
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

    assert rc.hooks_status(".") == 0


@pytest.mark.usefixtures("repo")
def test_hooks_status_is_inactive_when_the_hooks_belong_to_another_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session-other")
    rc.hook_marker("test-session-other").write_text(str(tmp_path / "other-checkout"), encoding="utf-8")

    assert rc.hooks_status(".") == 1


@pytest.mark.usefixtures("repo")
def test_hooks_status_is_inactive_when_no_hook_ran(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session-none")
    rc.hook_marker("test-session-none").unlink(missing_ok=True)

    assert rc.hooks_status(".") == 1


def test_inactive_hooks_print_a_context_block_for_subagent_prompts(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session-block")
    monkeypatch.setattr("sys.argv", ["repo-context.py", "--hooks-status", "--base", "stable"])

    assert rc.main() == 1
    block = capsys.readouterr().out
    assert f"Reviewed checkout: {repo.resolve()}" in block
    assert f"- frontend: {repo.resolve() / '.agents/rules/code-doc-style.md'}" in block
    assert f"- {repo.resolve() / 'AGENTS.md'}" in block


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


def test_paths_from_bash_skip_a_token_longer_than_a_file_name(repo: Path) -> None:
    command = f"git commit -m {'a' * 300} frontend/app/src/page.tsx"

    assert rc.paths_from_tool("Bash", {"command": command}, repo, repo.resolve()) == ["frontend/app/src/page.tsx"]


def test_instructions_for_a_directory_match_every_tracked_file(repo: Path) -> None:
    for index in range(250):
        write(repo, f"frontend/app/assets/{index:03}.txt")
    run("add", "frontend", cwd=repo)

    assert ".agents/rules/frontend.md" in rc.instructions_for(["frontend"])


def run_bash_hook(repo: Path, monkeypatch: pytest.MonkeyPatch, command: str, capsys: pytest.CaptureFixture[str]) -> str:
    payload = {
        "session_id": "test-session-budget",
        "cwd": str(repo),
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert rc.run_hook() == 0
    return capsys.readouterr().out


def test_hook_names_a_document_over_the_budget_once(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write(repo, "frontend/app/AGENTS.md", "x" * rc.HOOK_BUDGET)
    run("add", "frontend/app/AGENTS.md", cwd=repo)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))

    first = run_bash_hook(repo, monkeypatch, "cat frontend/app/src/page.tsx", capsys)
    second = run_bash_hook(repo, monkeypatch, "cat frontend/app/src/page.tsx", capsys)

    assert "too long to include here" in json.loads(first)["hookSpecificOutput"]["additionalContext"]
    assert not second


def test_hook_retries_a_document_crowded_out_by_others(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write(repo, "frontend/app/AGENTS.md", "x" * (rc.HOOK_BUDGET // 2))
    write(repo, "frontend/app/src/AGENTS.md", "y" * (rc.HOOK_BUDGET // 2))
    run("add", "frontend", cwd=repo)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))

    first = run_bash_hook(repo, monkeypatch, "ls frontend/app", capsys)
    second = run_bash_hook(repo, monkeypatch, "cat frontend/app/src/page.tsx", capsys)

    assert "included on a later call: frontend/app/src/AGENTS.md" in first
    assert "## frontend/app/src/AGENTS.md" in json.loads(second)["hookSpecificOutput"]["additionalContext"]
