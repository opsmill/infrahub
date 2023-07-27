import logging

import typer
import uvicorn

app = typer.Typer()


@app.callback()
def callback():
    """
    Control the API Server.
    """


log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "default": {"formatter": "default", "class": "logging.NullHandler"},
        "access": {"formatter": "access", "class": "logging.NullHandler"},
    },
    "loggers": {
        "uvicorn.error": {"level": "INFO", "handlers": ["default"], "propagate": True},
        "uvicorn.access": {"level": "INFO", "handlers": ["access"], "propagate": False},
    },
}


@app.command()
def start(
    listen: str = typer.Option("127.0.0.1", help="Address used to listen for new request."),
    port: int = typer.Option(8000, help="Port used to listen for new request."),
    debug: bool = typer.Option(False, help="Enable advanced logging and troubleshooting"),
):
    """Start Infrahub in Debug Mode with reload enabled."""

    # it's not possible to pass the location of the config file directly to uvicorn.run
    # so we must rely on the environment variable

    logging.getLogger("neo4j").setLevel(logging.ERROR)

    if debug:
        uvicorn.run(
            "infrahub.server:app",
            host=listen,
            port=port,
            log_level="info",
            reload=True,
            reload_excludes=["examples", "repositories"],
            log_config=log_config,
        )
    else:
        uvicorn.run(
            "infrahub.server:app",
            host=listen,
            port=port,
            log_level="info",
            log_config=log_config,
        )


# gunicorn infrahub.server:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
