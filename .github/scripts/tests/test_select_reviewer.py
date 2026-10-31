"""Tests for the pull request reviewer selection script, run against throwaway git repositories."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess  # noqa: S404
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).parents[1] / "select_reviewer.py"
REPO_ROOT = Path(__file__).parents[3]
_spec = importlib.util.spec_from_file_location("select_reviewer", SCRIPT)
if _spec is None or _spec.loader is None:
    raise ImportError(SCRIPT)
sr = importlib.util.module_from_spec(_spec)
sys.modules["select_reviewer"] = sr
_spec.loader.exec_module(sr)

NOW = "2026-09-01T12:00:00+00:00"


def days_ago(n: int) -> str:
    return (datetime.fromisoformat(NOW) - timedelta(days=n)).isoformat()


class Repo:
    """A git repository whose commits carry chosen authors and dates."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.git("init", "-q", "-b", "main")

    def git(self, *args: str, env: dict[str, str] | None = None) -> str:
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(self.path), *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, **(env or {})},
        ).stdout

    def commit(self, login: str, files: list[str], age_days: int) -> str:
        for name in files:
            target = self.path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as fh:
                fh.write(f"{login} {age_days}\n")
        self.git("add", *files)
        when = days_ago(age_days)
        email = f"{login}@users.noreply.github.com"
        env = {
            "GIT_AUTHOR_NAME": login,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_AUTHOR_DATE": when,
            "GIT_COMMITTER_NAME": login,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_COMMITTER_DATE": when,
        }
        self.git("commit", "-q", "-m", f"change by {login}", env=env)
        return self.git("rev-parse", "HEAD").strip()


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo(tmp_path)


def make_config(**extra: Any) -> dict[str, Any]:  # noqa: ANN401
    config: dict[str, Any] = {
        "reviewers": ["alice", "bob", "carol", "dave"],
        "overrides": [],
        "fallback": [{"paths": ["**"], "reviewers": ["alice", "bob", "carol"]}],
        "ignore": ["**/*.lock", "changelog/**"],
        "bot_authors": ["helper[bot]"],
        "away": [],
        "load_cap": 3,
        "review_weight": 0.5,
    }
    return config | extra


def make_pr(files: list[str], author: str = "erin", number: int = 1, **extra: Any) -> dict[str, Any]:  # noqa: ANN401
    pr: dict[str, Any] = {
        "number": number,
        "author": author,
        "created_at": NOW,
        "files": [{"path": f, "lines": 10} for f in files],
        "commits": [],
    }
    return pr | extra


def decide(
    repo: Repo,
    config: dict[str, Any],
    pr: dict[str, Any],
    reviews: list[dict[str, Any]] | None = None,
    loads: dict[str, int] | None = None,
) -> dict[str, Any]:
    inputs = sr.Inputs(repo=repo.path, pr=pr, reviews=reviews or [], logins={}, loads=loads or {}, at=sr.iso_ts(NOW))
    return sr.decide(config, inputs)


def picked(result: dict[str, Any]) -> str | None:
    return (result["decision"] or {}).get("login")


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("frontend/app/src/main.tsx", "frontend/**", True),
        ("frontend", "frontend/**", False),
        ("backend/tests/unit/git/test_sync.py", "backend/tests/**/git/**", True),
        ("backend/tests/git/test_sync.py", "backend/tests/**/git/**", True),
        ("backend/infrahub/core/diff.py", "backend/infrahub/*.py", False),
        ("uv.lock", "**/*.lock", True),
        ("python_sdk", "python_sdk", True),
    ],
)
def test_glob_match(path: str, pattern: str, expected: bool) -> None:
    assert sr.glob_match(path, pattern) is expected


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        ({"head_repo": "someone/fork"}, "pull request from another repository"),
        ({"draft": True}, "draft pull request"),
        ({"author": "other[bot]", "author_is_bot": True}, "opened by a bot"),
        ({"requested_users": ["alice"]}, "already has an individual reviewer"),
        ({"reviewed_by": ["bob"]}, "already has an individual reviewer"),
        ({"author": "helper[bot]", "author_is_bot": True}, None),
        ({"reviewed_by": ["erin"]}, None),
        ({}, None),
    ],
)
def test_gate(extra: dict[str, Any], reason: str | None) -> None:
    pr = make_pr(["backend/a.py"], head_repo="opsmill/infrahub") | extra
    assert sr.gate(make_config(), pr, "opsmill/infrahub") == reason


def test_score_picks_the_most_recent_contributor_who_is_not_the_author(repo: Repo) -> None:
    repo.commit("bob", ["backend/a.py"], age_days=300)
    repo.commit("carol", ["backend/a.py"], age_days=10)
    repo.commit("carol", ["backend/a.py"], age_days=5)
    repo.commit("erin", ["backend/a.py"], age_days=1)

    result = decide(repo, make_config(), make_pr(["backend/a.py"]))

    assert picked(result) == "carol"
    assert result["decision"]["source"].startswith("score")
    assert result["backups"][0] == "bob"


def test_commits_of_the_pull_request_itself_do_not_count(repo: Repo) -> None:
    repo.commit("bob", ["backend/a.py"], age_days=100)
    own = repo.commit("carol", ["backend/a.py"], age_days=1)

    result = decide(repo, make_config(), make_pr(["backend/a.py"], author="dave", commits=[own]))

    assert picked(result) == "bob"


def test_review_history_counts_only_before_the_pull_request(repo: Repo) -> None:
    repo.commit("bob", ["backend/a.py"], age_days=50)
    reviews = [
        {"merged_at": days_ago(20), "files": ["backend/a.py"], "reviewers": ["carol"]},
        {"merged_at": days_ago(10), "files": ["backend/a.py"], "reviewers": ["carol"]},
        {"merged_at": days_ago(-5), "files": ["backend/a.py"], "reviewers": ["dave", "dave"]},
    ]

    result = decide(repo, make_config(review_weight=0.8), make_pr(["backend/a.py"]), reviews=reviews)

    assert picked(result) == "carol"
    assert "dave" not in [c["login"] for c in result["chain"]]


def test_people_outside_the_reviewer_list_are_never_picked(repo: Repo) -> None:
    repo.commit("mallory", ["backend/a.py"], age_days=1)
    repo.commit("bob", ["backend/a.py"], age_days=200)

    result = decide(repo, make_config(), make_pr(["backend/a.py"]))

    assert picked(result) == "bob"
    assert {"login": "mallory", "skip": "not a listed reviewer"}.items() <= result["chain"][0].items()


def test_an_override_wins_over_the_score_and_ignores_the_load_cap(repo: Repo) -> None:
    repo.commit("bob", ["frontend/app.tsx"], age_days=1)
    override = {"name": "Frontend by erin", "reason": "test", "author": "erin", "paths": ["frontend/**"]}
    config = make_config(overrides=[override | {"reviewers": ["zoe"]}])

    result = decide(repo, config, make_pr(["frontend/app.tsx"]), loads={"zoe": 9})

    assert picked(result) == "zoe"
    assert result["decision"]["source"] == "override: Frontend by erin"
    assert result["backups"] == ["bob", "carol"]


def test_an_override_needs_its_author_and_its_paths_to_match(repo: Repo) -> None:
    repo.commit("bob", ["backend/a.py"], age_days=1)
    override = {"name": "o", "reason": "test", "author": "erin", "paths": ["frontend/**"], "reviewers": ["zoe"]}
    config = make_config(overrides=[override])

    assert picked(decide(repo, config, make_pr(["backend/a.py"]))) == "bob"
    assert picked(decide(repo, config, make_pr(["backend/a.py"], author="dave"))) == "bob"


@pytest.mark.parametrize("config_extra", [{"away": ["zoe"]}, {}])
def test_an_override_reviewer_who_is_away_or_the_author_falls_back_to_the_score(
    repo: Repo, config_extra: dict[str, Any]
) -> None:
    repo.commit("bob", ["backend/a.py"], age_days=1)
    override = {"name": "o", "reason": "test", "paths": ["backend/**"], "reviewers": ["zoe"]}
    config = make_config(overrides=[override]) | config_extra
    author = "erin" if config_extra else "zoe"

    result = decide(repo, config, make_pr(["backend/a.py"], author=author))

    assert picked(result) == "bob"


def test_reviewers_at_the_load_cap_are_skipped(repo: Repo) -> None:
    repo.commit("bob", ["backend/a.py"], age_days=1)
    repo.commit("carol", ["backend/a.py"], age_days=100)

    result = decide(repo, make_config(), make_pr(["backend/a.py"]), loads={"bob": 3, "carol": 2})

    assert picked(result) == "carol"
    assert result["chain"][0]["skip"] == "load 3 >= cap 3"


def test_when_everyone_is_at_the_cap_the_least_loaded_is_picked(repo: Repo) -> None:
    repo.commit("bob", ["backend/a.py"], age_days=1)
    loads = {"alice": 5, "bob": 4, "carol": 3, "dave": 6}

    result = decide(repo, make_config(), make_pr(["backend/a.py"]), loads=loads)

    assert picked(result) == "carol"
    assert result["decision"]["source"].endswith("least loaded (everyone at the cap)")


def test_without_history_the_fallback_rotates_by_pull_request_number(repo: Repo) -> None:
    repo.commit("erin", ["docs/readme.md"], age_days=1)
    config = make_config()

    picks = [picked(decide(repo, config, make_pr(["docs/readme.md"], number=n))) for n in (0, 1, 2, 3)]

    assert picks == ["alice", "bob", "carol", "alice"]


def test_the_fallback_prefers_the_least_loaded(repo: Repo) -> None:
    repo.commit("erin", ["docs/readme.md"], age_days=1)

    result = decide(
        repo, make_config(), make_pr(["docs/readme.md"], number=0), loads={"alice": 2, "bob": 1, "carol": 0}
    )

    assert picked(result) == "carol"


def test_ignored_files_neither_match_nor_score(repo: Repo) -> None:
    repo.commit("bob", ["uv.lock", "backend/a.py"], age_days=1)

    assert decide(repo, make_config(), make_pr(["uv.lock", "changelog/1.added.md"]))["reason"] == "only ignored files"


def test_bulk_commits_do_not_count(repo: Repo) -> None:
    repo.commit("bob", [f"backend/f{i}.py" for i in range(sr.BULK_FILES + 1)], age_days=1)
    repo.commit("carol", ["backend/f0.py"], age_days=200)

    assert picked(decide(repo, make_config(), make_pr(["backend/f0.py"]))) == "carol"


def test_a_new_file_counts_through_its_folder(repo: Repo) -> None:
    repo.commit("bob", ["backend/git/sync.py"], age_days=3)
    repo.commit("carol", ["backend/other.py"], age_days=1)

    assert picked(decide(repo, make_config(), make_pr(["backend/git/new_module.py"]))) == "bob"


def test_check_reports_config_problems(repo: Repo) -> None:
    repo.commit("bob", ["backend/a.py"], age_days=1)
    config = make_config(
        overrides=[{"name": "o", "reviewers": ["zoe"]}],
        fallback=[{"paths": ["nowhere/**"], "reviewers": ["zoe"]}],
        load_cap=0,
    )

    problems = sr.check(config, repo.path)

    assert problems == [
        "override 'o': missing reason",
        "override 'o': needs an author, paths or both",
        "fallback: zoe is not in reviewers",
        "fallback: pattern matches no file: nowhere/**",
        "load_cap: expected a positive integer",
    ]


def test_the_repository_config_is_valid() -> None:
    config = sr.load_config(REPO_ROOT / sr.DEFAULT_CONFIG)

    assert sr.check(config, REPO_ROOT) == []


def test_main_writes_the_login_for_the_workflow(repo: Repo, tmp_path_factory: pytest.TempPathFactory) -> None:
    repo.commit("bob", ["backend/a.py"], age_days=1)
    tmp_path = tmp_path_factory.mktemp("inputs")
    files = {
        "config.json": make_config(),
        "pr.json": make_pr(["backend/a.py"], number=7),
        "reviews.json": [],
        "loads.json": {},
    }
    for name, data in files.items():
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    output, step_summary = tmp_path / "output", tmp_path / "summary.md"

    sr.main(
        [
            *("--repo", str(repo.path), "--config", str(tmp_path / "config.json")),
            *("--pr-json", str(tmp_path / "pr.json"), "--reviews-json", str(tmp_path / "reviews.json")),
            *("--loads-json", str(tmp_path / "loads.json"), "--at", NOW, "--out", str(tmp_path / "out.json")),
            *("--github-output", str(output), "--summary", str(step_summary)),
        ]
    )

    assert output.read_text(encoding="utf-8") == "login=bob\n"
    assert "Requested: `bob`" in step_summary.read_text(encoding="utf-8")
