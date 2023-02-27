import os
from pathlib import Path


def get_fixtures_dir() -> Path:
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = os.path.abspath(os.path.dirname(__file__))
    fixtures_dir = os.path.join(here, "..", "tests", "fixtures")

    return Path(os.path.abspath(fixtures_dir))
