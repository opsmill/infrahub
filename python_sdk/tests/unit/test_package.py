from pathlib import Path

import pytest
import toml


@pytest.fixture
def pyproject_file() -> Path:
    return Path("python_sdk/pyproject.toml")


def test_pyproject_all_extra_dependencies(pyproject_file):
    pyproject = toml.loads(pyproject_file.read_text())

    try:
        extras = pyproject["tool"]["poetry"]["extras"]
    except KeyError:
        pytest.skip("extras not defined in pyproject.toml")

    all_extras = extras.pop("all", [])

    groups_extras = {dependency for extra in extras.values() for dependency in extra}

    assert set(all_extras) == groups_extras
