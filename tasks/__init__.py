"""Replacement for Makefile."""
import os

from invoke import Collection, Context, Exit, task

from . import backend, ctl, demo, main, nornir, performance, sdk, sync, test

ns = Collection()
ns.add_collection(sdk)
ns.add_collection(performance)
ns.add_collection(ctl)
ns.add_collection(nornir)
ns.add_collection(backend)
ns.add_collection(demo)
ns.add_collection(main)
ns.add_collection(sync)
ns.add_collection(test)

@task
def yamllint(context: Context):
    """This will run yamllint to validate formatting of all yaml files."""

    exec_cmd = "yamllint ."
    context.run(exec_cmd, pty=True)


@task(name="schema-generate-doc")
def generate_schema_doc(context: Context):
    """Generate documentation for the schema"""

    from pathlib import Path

    import jinja2

    from infrahub.core.schema import internal_schema

    schemas_to_generate = ["10_node", "20_attribute", "30_relationship", "40_generic"]
    here = os.path.abspath(os.path.dirname(__file__))

    for schema_name in schemas_to_generate:
        template_file = os.path.join(here, f"../docs/15_schema/{schema_name}.j2")
        output_file = os.path.join(here, f"../docs/15_schema/{schema_name}.md")
        if not os.path.exists(template_file):
            raise Exit(f"Unable to find the template file at {template_file}")

        template_text = Path(template_file).read_text()

        environment = jinja2.Environment()
        template = environment.from_string(template_text)
        rendered_file = template.render(schema=internal_schema)

        with open(output_file, "w") as f:
            f.write(rendered_file)

        print(f"Schema generated for {schema_name}")

    print("Schema documentation generated")


@task(name="format")
def format_all(context: Context):
    main.format_all(context)
    sdk.format_all(context)
    nornir.format_all(context)
    backend.format_all(context)
    ctl.format_all(context)
    sync.format_all(context)


@task(name="lint")
def lint_all(context: Context):
    yamllint(context)
    sdk.lint(context)
    nornir.lint(context)
    backend.lint(context)
    ctl.lint(context)
    sync.lint(context)


@task(name="generate-doc")
def generate_doc(context: Context):
    backend.generate_doc(context)
    ctl.generate_doc(context)


ns.add_task(format_all)
ns.add_task(lint_all)
ns.add_task(yamllint)
ns.add_task(generate_schema_doc)
ns.add_task(generate_doc)
