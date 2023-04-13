import glob
import os
from pathlib import Path
from typing import List, Optional, Union

import httpx
import pendulum
from pendulum.datetime import DateTime


def calculate_time_diff(value: str) -> Optional[str]:
    """Calculate the time in human format between a timedate in string format and now."""
    try:
        time_value = pendulum.parse(value)
    except pendulum.parsing.exceptions.ParserError:
        return None

    if not isinstance(time_value, DateTime):
        return None

    pendulum.set_locale("en")
    return time_value.diff_for_humans(other=pendulum.now(), absolute=True)


def execute_query(
    query: str,
    server: str = "http://localhost",
    variables: Optional[dict] = None,
    branch: str = "main",
    rebase: bool = False,
    at: Optional[str] = None,
    timeout: int = 10,
    params: Optional[dict] = None,
) -> dict:
    """Execute a GraphQL Query via the GraphQL API endpoint."""
    payload = {"query": query, "variables": variables}
    params = params if params else {}

    if at and "at" not in params:
        params["at"] = at
    if "rebase" not in params:
        params["rebase"] = str(rebase)

    response = httpx.post(f"{server}/graphql/{branch}", json=payload, timeout=timeout, params=params)
    response.raise_for_status()
    return response.json()


def find_graphql_query(name: str, directory: Union[str, Path] = ".") -> str:
    for query_file in glob.glob(f"{directory}/**/*.gql", recursive=True):
        filename = os.path.basename(query_file)
        query_name = os.path.splitext(filename)[0]

        if query_name != name:
            continue
        with open(query_file, "r", encoding="UTF-8") as file_data:
            query_string = file_data.read()

        return query_string

    return ""


def find_files(
    extension: Union[str, List[str]], directory: Union[str, Path] = ".", recursive: bool = True
) -> List[str]:
    files = []

    if isinstance(extension, str):
        files.extend(glob.glob(f"{directory}/**/*.{extension}", recursive=recursive))
        files.extend(glob.glob(f"{directory}/**/.*.{extension}", recursive=recursive))
    elif isinstance(extension, list):
        for ext in extension:
            files.extend(glob.glob(f"{directory}/**/*.{ext}", recursive=recursive))
            files.extend(glob.glob(f"{directory}/**/.*.{ext}", recursive=recursive))
    return files


def render_action_rich(value: str) -> str:
    if value == "created":
        return f"[green]{value.upper()}[/green]"
    if value == "updated":
        return f"[magenta]{value.upper()}[/magenta]"
    if value == "deleted":
        return f"[red]{value.upper()}[/red]"

    return value.upper()


def get_fixtures_dir() -> Path:
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = os.path.abspath(os.path.dirname(__file__))
    fixtures_dir = os.path.join(here, "..", "tests", "fixtures")

    return Path(os.path.abspath(fixtures_dir))
