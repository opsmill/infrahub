from __future__ import annotations

from pathlib import Path

import pytest

from dependabot_autopilot.codeowners import owners_for

REPO_CODEOWNERS = (Path(__file__).parent / "fixtures" / "CODEOWNERS").read_text(encoding="utf-8")
FALLBACK = "@opsmill/dependency-reviewers"


def owners(*paths: str, codeowners_text: str = REPO_CODEOWNERS) -> tuple[str, ...]:
    return owners_for(paths=paths, codeowners_text=codeowners_text, fallback=FALLBACK)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("uv.lock", ("@opsmill/backend",)),
        ("python_testcontainers/uv.lock", ("@opsmill/backend",)),
        ("pyproject.toml", ("@opsmill/backend",)),
        ("backend/infrahub/server.py", ("@opsmill/backend",)),
        ("frontend/pnpm-lock.yaml", ("@opsmill/frontend",)),
        ("docker-compose.yml", ("@opsmill/cloud",)),
        ("dev/guidelines/backend/python.md", ("@opsmill/backend",)),
        ("docs/package-lock.json", ("@opsmill/product", "@opsmill/sa")),
    ],
)
def test_repository_codeowners(path: str, expected: tuple[str, ...]) -> None:
    assert owners(path) == expected


def test_github_directory_has_no_owner_so_fallback_applies() -> None:
    assert owners(".github/workflows/ci.yml") == (FALLBACK,)


def test_rule_without_owners_clears_earlier_match() -> None:
    assert owners("frontend/app/src/shared/api/rest/types.generated.ts") == (FALLBACK,)
    assert owners("frontend/app/src/shared/api/graphql/generated/graphql.ts") == (FALLBACK,)


def test_last_matching_rule_wins() -> None:
    assert owners("docs/docs/reference/schema.mdx") == ("@opsmill/backend", "@opsmill/frontend")
    assert owners("docs/docs/guides/intro.mdx") == ("@opsmill/backend", "@opsmill/frontend", "@opsmill/sa")


def test_owners_of_several_paths_are_merged_and_unowned_paths_add_no_fallback() -> None:
    assert owners("uv.lock", "frontend/package.json", ".github/dependabot.yml") == (
        "@opsmill/backend",
        "@opsmill/frontend",
    )


def test_comment_and_blank_lines_are_ignored() -> None:
    text = "# uv.lock @opsmill/nobody\n\n   \n  # indented comment\nuv.lock @opsmill/backend\n"

    assert owners("uv.lock", codeowners_text=text) == ("@opsmill/backend",)
    assert owners("README.md", codeowners_text=text) == (FALLBACK,)


@pytest.mark.parametrize(
    ("pattern", "path", "matches"),
    [
        ("*.js", "src/app/index.js", True),
        ("*.js", "index.ts", False),
        ("/build/logs/", "build/logs/2026/app.log", True),
        ("/build/logs/", "src/build/logs/app.log", False),
        ("apps/", "services/apps/main.py", True),
        ("apps/", "apps", False),
        ("docs/*", "docs/getting-started.md", True),
        ("docs/*", "docs/build-app/troubleshooting.md", False),
        ("docs/*", "nested/docs/getting-started.md", False),
        ("**/logs", "deeply/nested/logs/app.log", True),
        ("**/logs", "logs/app.log", True),
        ("/src/**/test.py", "src/test.py", True),
        ("/src/**/test.py", "src/a/b/test.py", True),
        ("/src/**/test.py", "lib/src/test.py", False),
        ("/scripts/**", "scripts/tools/run.sh", True),
        ("/docs", "docs/index.md", True),
        ("/docs", "documentation/index.md", False),
        ("/.github/*.yml", ".github/labels.yml", True),
        ("/.github/*.yml", ".github/workflows/ci.yml", False),
        ("?.txt", "a.txt", True),
        ("?.txt", "ab.txt", False),
        ("uv.lock", "uv.lock.bak", False),
    ],
)
def test_github_pattern_semantics(pattern: str, path: str, matches: bool) -> None:
    expected = ("@owner",) if matches else (FALLBACK,)

    assert owners(path, codeowners_text=f"{pattern} @owner\n") == expected
