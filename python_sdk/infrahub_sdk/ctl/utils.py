import glob
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

import pendulum
from pendulum.datetime import DateTime
from rich.console import Console
from rich.markup import escape
from rich.progress import Progress, SpinnerColumn, TextColumn

from infrahub_sdk.ctl.exceptions import QueryNotFoundError

from .client import initialize_client_sync


def execute_graphql_query(
    query: str, variables_dict: Dict[str, Any], branch: Optional[str] = None, debug: bool = False
) -> Dict:
    console = Console()
    query_str = find_graphql_query(query)

    client = initialize_client_sync()
    response = client.execute_graphql(
        query=query_str,
        branch_name=branch,
        variables=variables_dict,
        raise_for_error=False,
    )

    if debug:
        message = ("-" * 40, f"Response for GraphQL Query {query}", response, "-" * 40)
        console.print("\n".join(message))

    return response


def print_graphql_errors(console: Console, errors: List) -> None:
    if not isinstance(errors, list):
        console.print(f"[red]{escape(str(errors))}")

    for error in errors:
        if isinstance(error, dict) and "message" in error and "path" in error:
            console.print(f"[red]{escape(str(error['path']))} {escape(str(error['message']))}")
        else:
            console.print(f"[red]{escape(str(error))}")


def parse_cli_vars(variables: Optional[List[str]]) -> dict:
    if not variables:
        return {}

    return {var.split("=")[0]: var.split("=")[1] for var in variables if "=" in var}


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


def find_graphql_query(name: str, directory: Union[str, Path] = ".") -> str:
    for query_file in glob.glob(f"{directory}/**/*.gql", recursive=True):
        filename = os.path.basename(query_file)
        query_name = os.path.splitext(filename)[0]

        if query_name != name:
            continue
        with open(query_file, "r", encoding="UTF-8") as file_data:
            query_string = file_data.read()

        return query_string

    raise QueryNotFoundError(name=name)


def render_action_rich(value: str) -> str:
    if value == "created":
        return f"[green]{value.upper()}[/green]"
    if value == "updated":
        return f"[magenta]{value.upper()}[/magenta]"
    if value == "deleted":
        return f"[red]{value.upper()}[/red]"

    return value.upper()


@contextmanager
def rich_progress_spinner(
    console: Optional[Console] = None, description: str = "Working", total: Optional[float] = None
) -> Generator:
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
        if console:
            task_id = progress.add_task(description=description, total=None)
        yield
        if console:
            progress.stop_task(task_id)


def get_fixtures_dir() -> Path:
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = Path(__file__).resolve().parent
    return here.parent.parent / "tests" / "fixtures"
