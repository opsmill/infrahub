"""Replacement for Makefile."""

from invoke import Collection, Context, task

from . import backend, demo, dev, docs, main, performance, schema, sdk
from .utils import ESCAPED_REPO_PATH

ns = Collection()
ns.add_collection(sdk)
ns.add_collection(dev)
ns.add_collection(docs)
ns.add_collection(performance)
ns.add_collection(backend)
ns.add_collection(demo)
ns.add_collection(main)
ns.add_collection(schema)


@task
def yamllint(context: Context) -> None:
    """This will run yamllint to validate formatting of all yaml files."""

    exec_cmd = "yamllint -s ."
    context.run(exec_cmd, pty=True)


@task(name="format")
def format_all(context: Context) -> None:
    main.format_all(context)
    backend.format_all(context)


@task(name="lint")
def lint_all(context: Context) -> None:
    yamllint(context)
    backend.lint(context)


@task
def pull(context: Context) -> None:
    """Pull the latest changes from Github and update the submodule to the proper commit."""
    commands = ["git pull", "git submodule update"]
    with context.cd(ESCAPED_REPO_PATH):
        for command in commands:
            context.run(command, pty=True)


ns.add_task(format_all)
ns.add_task(lint_all)
ns.add_task(yamllint)
ns.add_task(pull)
