"""Replacement for Makefile."""

from invoke import Collection, Context, task

from . import backend, demo, dev, docs, main, performance, schema, sdk, sync

ns = Collection()
ns.add_collection(sdk)
ns.add_collection(dev)
ns.add_collection(docs)
ns.add_collection(performance)
ns.add_collection(backend)
ns.add_collection(demo)
ns.add_collection(main)
ns.add_collection(schema)
ns.add_collection(sync)


@task
def yamllint(context: Context):
    """This will run yamllint to validate formatting of all yaml files."""

    exec_cmd = "yamllint ."
    context.run(exec_cmd, pty=True)


@task(name="format")
def format_all(context: Context):
    main.format_all(context)
    sdk.format_all(context)
    backend.format_all(context)
    sync.format_all(context)


@task(name="lint")
def lint_all(context: Context):
    yamllint(context)
    sdk.lint(context)
    backend.lint(context)
    sync.lint(context)


ns.add_task(format_all)
ns.add_task(lint_all)
ns.add_task(yamllint)
