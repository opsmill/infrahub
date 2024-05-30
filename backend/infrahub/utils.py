import hashlib
import os
from enum import Enum, EnumMeta
from pathlib import Path
from typing import Any, Dict, List, Optional

KWARGS_TO_DROP = ["session"]


def get_fixtures_dir() -> Path:
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = Path(__file__).parent.resolve()
    return here.parent / "tests" / "fixtures"


def get_models_dir() -> Path:
    """Get the directory which stores additional models."""
    here = Path(__file__).parent.resolve()
    return here.parent.parent / "models"


def find_first_file_in_directory(directory: str) -> Optional[str]:
    top_level_files = os.listdir(directory)
    for filename in top_level_files:
        full_filename = os.path.join(directory, filename)
        if os.path.isfile(full_filename):
            return filename

    return None


def format_label(slug: str) -> str:
    return " ".join([word.title() for word in slug.split("_")])


class MetaEnum(EnumMeta):
    def __contains__(cls, item: Any) -> bool:
        try:
            cls(item)  # pylint: disable=no-value-for-parameter
        except ValueError:
            return False
        return True


class BaseEnum(Enum, metaclass=MetaEnum):
    pass


class InfrahubNumberEnum(int, BaseEnum):
    @classmethod
    def available_types(cls) -> List[int]:
        return [cls.__members__[member].value for member in list(cls.__members__)]

    def get_hash(self) -> str:
        return hashlib.md5(str(self.value).encode(), usedforsecurity=False).hexdigest()


class InfrahubStringEnum(str, BaseEnum):
    @classmethod
    def available_types(cls) -> List[str]:
        return [cls.__members__[member].value for member in list(cls.__members__)]

    def get_hash(self) -> str:
        return hashlib.md5(self.value.encode(), usedforsecurity=False).hexdigest()


def get_nested_dict(nested_dict: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    current_level = nested_dict
    for key in keys:
        # Check if the key exists and leads to a dictionary
        if isinstance(current_level, dict) and key in current_level:
            current_level = current_level[key]
        else:
            return {}
    return current_level if isinstance(current_level, dict) else {}
