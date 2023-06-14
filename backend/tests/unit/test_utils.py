import os

from infrahub.utils import get_fixtures_dir


def test_get_fixtures_dir():
    assert os.path.exists(get_fixtures_dir())
