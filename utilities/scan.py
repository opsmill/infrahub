import logging
import os
import subprocess  # noqa: S404
import sys
from pathlib import Path


def find_keyword_violations(
    keywords: list[str],
    repo_root: Path,
    exclude_dirs: set[str],
    exclude_patterns: tuple[str, ...],
) -> list[str]:
    """
    Traverse files once and check each line for any prohibited keyword.

    Args:
        keywords: List of prohibited keywords (case-insensitive).
        repo_root: Root directory to scan.
        exclude_dirs: Set of directory names to exclude from scanning.
        exclude_patterns: Tuple of filename patterns to exclude.

    Returns:
        List of file paths (as strings) where any keyword was found.
    """
    violations = []
    lowered_keywords = [k.lower() for k in keywords]

    for path in repo_root.rglob("*"):
        if any(part in exclude_dirs for part in path.parts):
            continue
        if not path.is_file() or any(path.match(pat) for pat in exclude_patterns):
            continue
        try:
            with path.open(encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if any(keyword in line.lower() for keyword in lowered_keywords):
                        violations.append(str(path))
                        break
        except Exception:
            logging.exception(f"Error occurred while scanning {path}")
    return violations


def find_keyword_in_git_commits(keywords: list[str]) -> list[str]:
    """
    Scan git commit messages for any prohibited keyword.

    Args:
        keywords: List of prohibited keywords (case-insensitive).

    Returns:
        List of commit hashes where a prohibited keyword was found.
    """
    violations = []
    lowered_keywords = [k.lower() for k in keywords]
    try:
        result = subprocess.run(
            ["/usr/bin/git", "log", "--pretty=format:%H:%s"],
            capture_output=True,
            encoding="utf-8",
            check=True,
        )
        for line in result.stdout.splitlines():
            try:
                commit_hash, message = line.split(":", 1)
            except ValueError:
                continue
            if any(keyword in message.lower() for keyword in lowered_keywords):
                violations.append(commit_hash)
    except Exception:
        logging.exception("Error occurred while scanning git commit messages")
    return violations


def main() -> None:
    """
    Scan the repository for prohibited keywords.

    This function traverses all files (excluding certain directories and patterns) once,
    checking each line for any of the keywords specified in the KEYWORDS_LIST environment variable.
    It also scans all git commit messages for prohibited keywords.
    If any matches are found, the script will exit with an error and print a summary.

    Args:
        None

    Returns:
        None

    Raises:
        SystemExit: If prohibited keywords are found or if KEYWORDS_LIST is not set.

    Examples:
        $ uv run python utilities/scan.py
    """
    keyword_list = os.environ.get("KEYWORDS_LIST", "")
    if not keyword_list:
        print("::error::No KEYWORDS_LIST environment variable set")
        sys.exit(1)

    keywords = [k.strip() for k in keyword_list.split(",") if k.strip()]
    exclude_dirs = {".git", "node_modules"}
    exclude_patterns = ("*.log", "*.lock", ".env", "package-lock.json")
    repo_root = Path.cwd()

    violations = find_keyword_violations(keywords, repo_root, exclude_dirs, exclude_patterns)
    commit_violations = find_keyword_in_git_commits(keywords)

    if violations or commit_violations:
        if violations:
            print(f"::error::Keyword scan failed - prohibited terms found in {len(violations)} file(s)")
        if commit_violations:
            print(f"::error::Prohibited keywords found in {len(commit_violations)} git commit(s)")
        print("Contact security team for details on specific violations")
        sys.exit(1)
    else:
        print("✅ No prohibited keywords found in files or git commit messages")


if __name__ == "__main__":
    main()
