from pathlib import Path


def get_fixtures_dir() -> Path:
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = Path(__file__).parent.resolve()
    return here.parent / "fixtures"
