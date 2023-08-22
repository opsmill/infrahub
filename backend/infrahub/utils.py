import os
from enum import Enum, EnumMeta
from typing import List, Optional

KWARGS_TO_DROP = ["session"]


def get_fixtures_dir():
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = os.path.abspath(os.path.dirname(__file__))
    fixtures_dir = os.path.join(here, "..", "tests", "fixtures")

    return os.path.abspath(fixtures_dir)


def get_models_dir():
    """Get the directory which stores additional models."""
    here = os.path.abspath(os.path.dirname(__file__))
    models_dir = os.path.join(here, "..", "..", "models")

    return os.path.abspath(models_dir)


def find_first_file_in_directory(directory: str) -> Optional[str]:
    top_level_files = os.listdir(directory)
    for filename in top_level_files:
        full_filename = os.path.join(directory, filename)
        if os.path.isfile(full_filename):
            return filename

    return None


class MetaEnum(EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)  # pylint: disable=no-value-for-parameter
        except ValueError:
            return False
        return True


class BaseEnum(Enum, metaclass=MetaEnum):
    pass


class InfrahubStringEnum(str, BaseEnum):
    @classmethod
    def available_types(cls) -> List[str]:
        return [cls.__members__[member].value for member in list(cls.__members__)]
