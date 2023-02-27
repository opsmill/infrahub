import sys
from distutils.util import strtobool
from typing import Tuple

from invoke import Context, task  # type: ignore  # pylint: disable=import-error

try:
    import toml
except ImportError:
    sys.exit("Please make sure to `pip install toml` or enable the Poetry shell and run `poetry install`.")


def project_ver() -> str:
    """Find version from pyproject.toml to use for docker image tagging."""
    with open("pyproject.toml", encoding="UTF-8") as file:
        return toml.load(file)["tool"]["poetry"].get("version", "latest")


def git_info(context: Context) -> Tuple[str, str]:
    """Return the name of the current branch and hash of the current commit."""
    branch_name = context.run("git rev-parse --abbrev-ref HEAD", hide=True, pty=False)
    hash_value = context.run("git rev-parse --short HEAD", hide=True, pty=False)
    return branch_name.stdout.strip(), hash_value.stdout.strip()


def is_truthy(arg):
    """Convert "truthy" strings into Booleans.

    Examples:
        >>> is_truthy('yes')
        True
    Args:
        arg (str): Truthy string (True values are y, yes, t, true, on and 1; false values are n, no,
        f, false, off and 0. Raises ValueError if val is anything else.
    """
    if isinstance(arg, bool):
        return arg
    return bool(strtobool(arg))
