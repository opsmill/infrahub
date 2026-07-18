from pathlib import Path


def get_fixtures_dir() -> Path:
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = Path(__file__).parent.resolve()
    return here.parent / "fixtures"


def get_repository_dir() -> Path:
    """Get the repository root directory (the parent of `backend/`)."""
    here = Path(__file__).parent.resolve()
    return here.parent.parent.parent
