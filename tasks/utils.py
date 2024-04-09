import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Type, Union

from invoke import Context, UnexpectedExit

from infrahub.message_bus import InfrahubMessage, InfrahubResponse

try:
    import toml
except ImportError:
    sys.exit("Please make sure to `pip install toml` or enable the Poetry shell and run `poetry install`.")

path = Path(__file__)
TASKS_DIR = path.parent
REPO_BASE = TASKS_DIR.parent


def check_if_command_available(context: Context, command_name: str) -> bool:
    try:
        context.run(f"command -v {command_name}", hide=True)
        return True
    except UnexpectedExit:
        return False


def escape_path(path: Path) -> str:
    """Escape special characters in the provided path string to make it shell-safe."""
    return str(path).translate(
        str.maketrans(
            {
                "-": r"\-",
                "]": r"\]",
                "\\": r"\\",
                "^": r"\^",
                "$": r"\$",
                "*": r"\*",
                "(": r"\(",
                ")": r"\)",
                ".": r"\.",
            }
        )
    )


ESCAPED_REPO_PATH = escape_path(REPO_BASE)


def project_ver() -> str:
    """Find version from pyproject.toml to use for docker image tagging."""
    with open(f"{REPO_BASE}/pyproject.toml", encoding="UTF-8") as file:
        return toml.load(file)["tool"]["poetry"].get("version", "latest")


def git_info(context: Context) -> Tuple[str, str]:
    """Return the name of the current branch and hash of the current commit."""
    branch_name = context.run("git rev-parse --abbrev-ref HEAD", hide=True, pty=False)
    hash_value = context.run("git rev-parse --short HEAD", hide=True, pty=False)
    return branch_name.stdout.strip(), hash_value.stdout.strip()


def get_user_id(context: Context) -> int:
    user_id = context.run("id -u", hide=True, pty=False)
    clean_user_id = user_id.stdout.strip()
    return int(clean_user_id)


def get_group_id(context: Context) -> int:
    group_id = context.run("id -g", hide=True, pty=False)
    clean_user_id = group_id.stdout.strip()
    return int(clean_user_id)


def str_to_bool(value: str) -> bool:
    """Convert a String to a Boolean"""

    if isinstance(value, bool):
        return value

    if isinstance(value, int) and value in [0, 1]:
        return bool(value)

    if not isinstance(value, str):
        raise TypeError(f"{value} must be a string")

    MAP = {
        "y": True,
        "yes": True,
        "t": True,
        "true": True,
        "on": True,
        "1": True,
        "n": False,
        "no": False,
        "f": False,
        "false": False,
        "off": False,
        "0": False,
    }
    try:
        return MAP[value.lower()]
    except KeyError as exc:
        raise ValueError(f"{value} can not be converted into a boolean") from exc


def group_classes_by_category(
    classes: Dict[str, Type[Union[InfrahubMessage, InfrahubResponse]]], priority_map: Optional[Dict[str, int]] = None
) -> Dict[str, Dict[str, List[Dict[str, any]]]]:
    """
    Group classes into a nested dictionary by primary and secondary categories, including priority.
    """
    grouped = defaultdict(lambda: defaultdict(list))
    for event_name, cls in classes.items():
        parts = event_name.split(".")
        primary, secondary = parts[0], ".".join(parts[:2])
        priority = priority_map.get(event_name, 3) if priority_map else -1
        description = cls.__doc__.strip() if cls.__doc__ else None

        event_info = {
            "event_name": event_name,
            "description": description,
            "priority": priority,
            "fields": [
                {
                    "name": prop,
                    "type": details.get("type", "N/A"),
                    "description": details.get("description", "N/A"),
                    "default": details.get("default", "None"),
                }
                for prop, details in cls.model_json_schema().get("properties", {}).items()
            ],
        }
        grouped[primary][secondary].append(event_info)
    return grouped
