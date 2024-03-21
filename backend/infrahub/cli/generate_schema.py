from pathlib import Path

import typer
import ujson

app = typer.Typer()


@app.callback()
def callback() -> None:
    """
    Generate some Schema files used by Infrahub
    """


@app.command(name="schema")
def generate_schema(
    output_file: Path = typer.Argument("infrahub_schema.schema.json"),
) -> None:
    """Generate a the schema expected by infrahub for the schema `infrahubctl schema load`."""

    from infrahub.api.schema import (  # pylint: disable=import-outside-toplevel
        SchemaLoadAPI,
    )

    schema = SchemaLoadAPI.model_json_schema()

    schema["title"] = "InfrahubSchema"

    output_file.write_text(ujson.dumps(schema, indent=4))
    print(f"JSONSchema file saved in '{output_file}'")
