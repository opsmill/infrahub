import logging
import sys

import typer
from infrahub_sdk import Config, InfrahubClientSync
from infrahub_sdk.protocols import CoreGenericRepository

from infrahub import config
from infrahub.tls.context_builder import TlsContextBuilder

logging.getLogger("httpx").setLevel(logging.ERROR)
app = typer.Typer()


def build_client_config() -> Config:
    """Build the SDK configuration used to reach the Infrahub API, honouring the HTTP TLS settings.

    The helper runs as a git subprocess with its own process, so it has to apply the same TLS settings
    the task worker uses for its own client to the Infrahub API: without them an internal address served
    with a private CA is rejected.
    """
    client_config = Config(address=config.SETTINGS.main.internal_address, insert_tracker=True)
    tls_ca_bundle = config.SETTINGS.http.tls_ca_bundle
    client_config.set_ssl_context(
        context=TlsContextBuilder.build(
            insecure=config.SETTINGS.http.tls_insecure, ca_bundle=tls_ca_bundle, force_verify=bool(tls_ca_bundle)
        )
    )
    return client_config


def parse_helper_get_input(text: str) -> str:
    """Parse the input provided to infrahub-githelper get.

    Format1 (with usehttppath true)
      protocol=https
      host=github.com
      path=opsmill/infrahub-demo-edge.git

    Format2 (without usehttppath true)(default)
      protocol=https
      host=github.com

    Raises:
        ValueError: When the input is missing required keys or when ``path`` is not provided.

    """
    input_dict = {line.split("=")[0]: line.split("=")[1] for line in text.splitlines() if "=" in line}

    if "protocol" not in input_dict or "host" not in input_dict:
        raise ValueError("Input format not supported.")
    if "path" not in input_dict:
        raise ValueError(
            """Git usehttppath must be enabled to use this helper. You can active it with
    git config --global credential.usehttppath true
    """
        )

    return f"{input_dict['protocol']}://{input_dict['host']}/{input_dict['path']}"


@app.command()
def get(
    input_str: str = typer.Argument(... if sys.stdin.isatty() else sys.stdin.read().strip()),
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    config.SETTINGS.initialize_and_exit(config_file=config_file)

    try:
        location = parse_helper_get_input(text=input_str)
    except ValueError as exc:
        print(str(exc))
        raise typer.Exit(1) from exc

    client = InfrahubClientSync(config=build_client_config())
    repo = client.get(kind=CoreGenericRepository.__name__, location__value=location)

    if not repo:
        print("Repository not found in the database.")
        raise typer.Exit(1)

    if not repo.credential._id:
        print("Repository doesn't have credentials defined.")
        raise typer.Exit(1)

    repo.credential.fetch()

    print(f"username={repo.credential.peer.username.value}")
    print(f"password={repo.credential.peer.password.value}")


@app.command()
def store(
    input_str: str = typer.Argument(None),  # noqa: ARG001
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),  # noqa: ARG001
) -> None:
    raise typer.Exit()
