import asyncio
import logging
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Union

import pendulum
import typer
from httpx import HTTPError
from pendulum.datetime import DateTime
from rich.console import Console
from rich.logging import RichHandler
from rich.markup import escape

from infrahub_sdk.ctl.exceptions import QueryNotFoundError
from infrahub_sdk.exceptions import (
    AuthenticationError,
    Error,
    GraphQLError,
    ServerNotReachableError,
    ServerNotResponsiveError,
)

from .client import initialize_client_sync


def init_logging(debug: bool = False) -> None:
    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)

    log_level = "DEBUG" if debug else "INFO"
    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    logging.getLogger("infrahubctl")


def catch_exception(  # noqa: C901
    which_exception: Union[type[Exception], Iterable[type[Exception]]] = Exception,
    console: Optional[Console] = None,
    exit_code: int = 1,
):
    """Decorator to handle exception for commands."""
    if not console:
        console = Console()

    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any):
                try:
                    return await func(*args, **kwargs)
                except AuthenticationError as exc:
                    console.print(f"[red]Authentication failure: {str(exc)}")
                    raise typer.Exit(code=2)
                except (ServerNotReachableError, ServerNotResponsiveError) as exc:
                    console.print(f"[red]{str(exc)}")
                    raise typer.Exit(code=3)
                except HTTPError as exc:
                    console.print(f"[red]{str(exc)}")
                    raise typer.Exit(code=4)
                except GraphQLError as exc:
                    print_graphql_errors(console, exc.errors)
                    raise typer.Exit(code=5)
                except Error as exc:
                    console.print(f"[red]{str(exc)}")
                    raise typer.Exit(code=6)
                except which_exception as exc:
                    console.print(f"[red]{str(exc)}")
                    raise typer.Exit(code=exit_code)

            return async_wrapper

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            try:
                return func(*args, **kwargs)
            except AuthenticationError as exc:
                console.print(f"[red]Authentication failure: {str(exc)}")
                raise typer.Exit(code=2)
            except (ServerNotReachableError, ServerNotResponsiveError) as exc:
                console.print(f"[red]{str(exc)}")
                raise typer.Exit(code=3)
            except HTTPError as exc:
                console.print(f"[red]{str(exc)}")
                raise typer.Exit(code=4)
            except GraphQLError as exc:
                print_graphql_errors(console, exc.errors)
                raise typer.Exit(code=5)
            except Error as exc:
                console.print(f"[red]{str(exc)}")
                raise typer.Exit(code=6)
            except which_exception as exc:
                console.print(f"[red]{str(exc)}")
                raise typer.Exit(code=exit_code)

        return wrapper

    return decorator


def execute_graphql_query(
    query: str, variables_dict: dict[str, Any], branch: Optional[str] = None, debug: bool = False
) -> dict:
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


def print_graphql_errors(console: Console, errors: list) -> None:
    if not isinstance(errors, list):
        console.print(f"[red]{escape(str(errors))}")

    for error in errors:
        if isinstance(error, dict) and "message" in error and "path" in error:
            console.print(f"[red]{escape(str(error['path']))} {escape(str(error['message']))}")
        else:
            console.print(f"[red]{escape(str(error))}")


def parse_cli_vars(variables: Optional[list[str]]) -> dict[str, str]:
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
    if isinstance(directory, str):
        directory = Path(directory)

    for query_file in directory.glob("**/*.gql"):
        if query_file.stem != name:
            continue
        return query_file.read_text(encoding="utf-8")

    raise QueryNotFoundError(name=name)


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
    here = Path(__file__).resolve().parent
    return here.parent.parent / "tests" / "fixtures"
