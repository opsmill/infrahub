import logging
import os
import sys
from pathlib import Path

from invoke import Context, task

from .utils import ESCAPED_REPO_PATH, REPO_BASE

MAIN_DIRECTORY = Path("tasks")
NAMESPACE = "MAIN"


DIRECTORIES = [str(MAIN_DIRECTORY), "models", "utilities", "python_testcontainers"]

# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------


def _format_ruff(context: Context) -> None:
    """Run ruff to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with ruff")
    exec_cmd = f"poetry run ruff format {' '.join(DIRECTORIES)} --config {REPO_BASE / 'pyproject.toml'} && "
    exec_cmd += f"poetry run ruff check --fix {' '.join(DIRECTORIES)} --config {REPO_BASE / 'pyproject.toml'}"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task(name="format", default=True)
def format_all(context: Context) -> None:
    """This will run all formatters."""

    _format_ruff(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")


def _lint_ruff(context: Context) -> None:
    """Run ruff to check that Python files adherence to standards."""

    print(f" - [{NAMESPACE}] Check code with ruff")
    exec_cmd = f"poetry run ruff check --diff {' '.join(DIRECTORIES)} --config {REPO_BASE}/pyproject.toml"

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def lint(context: Context) -> None:
    """This will run all linters."""

    _lint_ruff(context)

    print(f" - [{NAMESPACE}] All linters have been executed!")


def _find_keyword_matches(
    repo_root: Path,
    keyword: str,
    exclude_dirs: set[str],
    exclude_patterns: tuple[str, ...],
) -> list[str]:
    """
    Search for files containing the given keyword, excluding specified directories and patterns.

    Args:
        repo_root: The root directory to search.
        keyword: The keyword to search for (case-insensitive).
        exclude_dirs: Set of directory names to exclude from the search.
        exclude_patterns: Tuple of filename patterns to exclude.

    Returns:
        List of file paths (as strings) where the keyword was found.

    Raises:
        OSError: If an error occurs while reading a file.

    Examples:
        matches = _find_keyword_matches(Path("."), "secret", {".git"}, ("*.log",))
    """
    matches: list[str] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in exclude_dirs for part in path.parts):
            continue
        if any(path.match(pat) for pat in exclude_patterns):
            continue
        try:
            with path.open(encoding="utf-8", errors="ignore") as f:
                if any(keyword.lower() in line.lower() for line in f):
                    matches.append(str(path))
        except Exception as exc:
            logging.exception(f"Error reading file {path}: {exc}")
            continue
    return matches


@task(name="scan")
def scan(context: Context) -> None:
    """
    Scan the repository for prohibited keywords.

    This function searches all files (excluding certain directories and patterns) for keywords
    specified in the KEYWORD_LIST environment variable. If any matches are found, the
    script will exit with an error and print a summary.

    Returns:
        None

    Raises:
        SystemExit: If prohibited keywords are found or if KEYWORD_LIST is not set.
    """

    keyword_list: str = os.environ.get("KEYWORD_LIST", "")
    if not keyword_list:
        print("::error::No KEYWORD_LIST environment variable set")
        sys.exit(1)

    keywords: list[str] = [k.strip() for k in keyword_list.split(",") if k.strip()]
    found: bool = False
    violations: list[str] = []

    exclude_dirs: set[str] = {".git", "node_modules"}
    exclude_patterns: tuple[str, ...] = ("*.log", "*.lock", ".env")

    repo_root: Path = Path.cwd()

    for keyword in keywords:
        matches = _find_keyword_matches(repo_root, keyword, exclude_dirs, exclude_patterns)
        if matches:
            violations.append(f"{len(matches)} file(s)")
            found = True

    if found:
        print(f"::error::Keyword scan failed - prohibited terms found in: {' '.join(violations)}")
        print("Contact security team for details on specific violations")
        sys.exit(1)
    else:
        print("✅ No prohibited keywords found")
