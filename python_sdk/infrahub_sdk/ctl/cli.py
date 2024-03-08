import sys

try:
    from .cli_commands import app
except ImportError as exc:
    sys.exit(
        f"Module {exc.name} is not available, install the 'ctl' extra of the infrahub-sdk package, `pip install 'infrahub-sdk[ctl]'` or enable the "
        "Poetry shell and run `poetry install --extras ctl`."
    )

__all__ = ["app"]
