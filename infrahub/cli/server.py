import typer
import uvicorn

import infrahub.config as config

app = typer.Typer()

TEST_DATABASE = "infrahub.testing2"


@app.command()
def start(config_file: str = "infrahub.toml", listen: str = "127.0.0.1", port: int = 8000, debug: bool = False):

    config.load_and_exit(config_file_name=config_file)

    """Start infrahub in Debug Mode with reload enabled."""

    if debug:
        uvicorn.run("infrahub.main:app", host=listen, port=port, log_level="info", reload=True)
    else:
        uvicorn.run("infrahub.main:app", host=listen, port=port, log_level="info")


# gunicorn infrahub.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
