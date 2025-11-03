from infrahub.utils import get_fixtures_dir


def test_get_fixtures_dir() -> None:
    assert get_fixtures_dir().exists()
