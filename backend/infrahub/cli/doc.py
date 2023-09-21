import os
from pathlib import Path

import jinja2
import typer

from infrahub.core.schema import internal_schema

app = typer.Typer()


DOCUMENTATION_DIRECTORY = "../../../docs"


@app.command()
def generate_schema():
    """Generate documentation for the schema"""

    schemas_to_generate = ["node", "attribute", "relationship", "generic"]
    here = os.path.abspath(os.path.dirname(__file__))

    for schema_name in schemas_to_generate:
        template_file = os.path.join(here, f"{DOCUMENTATION_DIRECTORY}/schema/{schema_name}.j2")
        output_file = os.path.join(here, f"{DOCUMENTATION_DIRECTORY}/schema/{schema_name}.md")
        if not os.path.exists(template_file):
            raise typer.Exit(f"Unable to find the template file at {template_file}")

        template_text = Path(template_file).read_text(encoding="utf-8")

        environment = jinja2.Environment()
        template = environment.from_string(template_text)
        rendered_file = template.render(schema=internal_schema)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(rendered_file)

        print(f"Schema generated for {schema_name}")

    print("Schema documentation generated")
