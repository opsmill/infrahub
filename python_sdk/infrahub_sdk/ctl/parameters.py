import typer

from infrahub_sdk.ctl import config


def load_configuration(value: str) -> str:
    """Load the configuration file using default environment variables or from the specified configuration file"""
    config.SETTINGS.load_and_exit(config_file=value)
    return value


CONFIG_PARAM = typer.Option(
    config.DEFAULT_CONFIG_FILE, "--config-file", envvar=config.ENVVAR_CONFIG_FILE, callback=load_configuration
)
