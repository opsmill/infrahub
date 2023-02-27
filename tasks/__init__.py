"""Replacement for Makefile."""

from invoke import (  # type: ignore  # pylint: disable=import-error
    Collection,
    Context,
    task,
)

from . import backend, ctl, demo, main, performance, sdk

# flake8: noqa: W605

ns = Collection()
ns.add_collection(sdk)
ns.add_collection(performance)
ns.add_collection(ctl)
ns.add_collection(backend)
ns.add_collection(demo)
ns.add_collection(main)


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
    ctl.format_all(context)


@task(name="lint")
def lint_all(context: Context):
    yamllint(context)
    sdk.lint(context)
    backend.lint(context)
    ctl.lint(context)


ns.add_task(format_all)
ns.add_task(lint_all)
ns.add_task(yamllint)
