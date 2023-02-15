import glob
import os
from typing import List, Union

import httpx
import pendulum


def calculate_time_diff(value: str) -> str:
    """Calculate the time in human format between a timedate in string format and now."""
    try:
        time_value = pendulum.parse(value)
    except pendulum.parsing.exceptions.ParserError:
        return None

    pendulum.set_locale("en")
    return time_value.diff_for_humans(other=pendulum.now(), absolute=True)


def execute_query(
    query,
    server: str = "http://localhost",
    variables: dict = None,
    branch: str = "main",
    rebase: bool = False,
    at=None,
    timeout: int = 10,
    params: dict = None,
):
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


def find_graphql_query(name, directory="."):
    for query_file in glob.glob(f"{directory}/**/*.gql", recursive=True):
        filename = os.path.basename(query_file)
        query_name = os.path.splitext(filename)[0]

        if query_name != name:
            continue
        with open(query_file, "r", encoding="UTF-8") as file_data:
            query_string = file_data.read()

        return query_string

    return None


def find_files(extension: Union[str, List[str]], directory=".", recursive: bool = True):
    files = []

    if isinstance(extension, str):
        files.extend(glob.glob(f"{directory}/**/*.{extension}", recursive=recursive))
        files.extend(glob.glob(f"{directory}/**/.*.{extension}", recursive=recursive))
    elif isinstance(extension, list):
        for ext in extension:
            files.extend(glob.glob(f"{directory}/**/*.{ext}", recursive=recursive))
            files.extend(glob.glob(f"{directory}/**/.*.{ext}", recursive=recursive))
    return files
