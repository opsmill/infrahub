import os
import sys
from pathlib import Path
from typing import Tuple

from invoke import Context

try:
    import toml
except ImportError:
    sys.exit("Please make sure to `pip install toml` or enable the Poetry shell and run `poetry install`.")

path = Path(__file__)
TASKS_DIR = str(path.parent)
REPO_BASE = os.path.join(TASKS_DIR, "..")


def project_ver() -> str:
    """Find version from pyproject.toml to use for docker image tagging."""
    with open(f"{REPO_BASE}/pyproject.toml", encoding="UTF-8") as file:
        return toml.load(file)["tool"]["poetry"].get("version", "latest")


def git_info(context: Context) -> Tuple[str, str]:
    """Return the name of the current branch and hash of the current commit."""
    branch_name = context.run("git rev-parse --abbrev-ref HEAD", hide=True, pty=False)
    hash_value = context.run("git rev-parse --short HEAD", hide=True, pty=False)
    return branch_name.stdout.strip(), hash_value.stdout.strip()
