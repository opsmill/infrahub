import logging
import os
import sys
from pathlib import Path


def main() -> None:
    keyword_list = os.environ.get("KEYWORD_LIST", "")
    if not keyword_list:
        print("::error::No KEYWORD_LIST environment variable set")
        sys.exit(1)

    keywords = [k.strip() for k in keyword_list.split(",") if k.strip()]
    found = False
    violations = []

    exclude_dirs = {".git", "node_modules"}
    exclude_patterns = ("*.log", "*.lock", ".env")

    repo_root = Path.cwd()

    def find_keyword_matches(
        keyword: str, repo_root: Path, exclude_dirs: set[str], exclude_patterns: tuple[str, ...]
    ) -> list[str]:
        matches = []
        for path in repo_root.rglob("*"):
            if any(part in exclude_dirs for part in path.parts):
                continue
            if not path.is_file() or any(path.match(pat) for pat in exclude_patterns):
                continue
            try:
                with path.open(encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if keyword.lower() in line.lower():
                            matches.append(str(path))
                            break
            except Exception:
                logging.exception(f"Error occurred while scanning {path}")
        return matches

    for keyword in keywords:
        matches = find_keyword_matches(keyword, repo_root, exclude_dirs, exclude_patterns)
        if matches:
            violations.append(f"{len(matches)} file(s)")
            found = True
            found = True

    if found:
        print(f"::error::Keyword scan failed - prohibited terms found in: {' '.join(violations)}")
        print("Contact security team for details on specific violations")
        sys.exit(1)
    else:
        print("✅ No prohibited keywords found")


if __name__ == "__main__":
    main()
