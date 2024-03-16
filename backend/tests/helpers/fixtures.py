import os


def get_fixtures_dir() -> str:
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = os.path.abspath(os.path.dirname(__file__))
    fixtures_dir = os.path.join(here, "../fixtures")

    return os.path.abspath(fixtures_dir)
