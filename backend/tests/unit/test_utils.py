from pathlib import Path

from infrahub.utils import get_fixtures_dir


def test_get_fixtures_dir():
    assert Path.exists(get_fixtures_dir())
