import typer
import uvicorn
import logging

app = typer.Typer()


@app.command()
def start(listen: str = "127.0.0.1", port: int = 8000, debug: bool = False):
    """Start Infrahub in Debug Mode with reload enabled."""

    # it's not possible to pass the location of the config file directly to uvicorn.run
    # so we must rely on the environment variable

    logging.getLogger("neo4j").setLevel(logging.ERROR)

    if debug:
        uvicorn.run(
            "infrahub.main:app",
            host=listen,
            port=port,
            log_level="info",
            reload=True,
            reload_excludes=["examples", "repositories"],
        )
    else:
        uvicorn.run("infrahub.main:app", host=listen, port=port, log_level="info")


# gunicorn infrahub.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
