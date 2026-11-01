from pathlib import Path

TESTS_DIR = Path(__file__).parent.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
FIXTURE_REPOS_DIR = FIXTURES_DIR / "repos"
REPOSITORY_ROOT = TESTS_DIR.parent.parent
DOCUMENTATION_ROOT = Path(__file__).resolve().parents[3] / "docs" / "docs"
