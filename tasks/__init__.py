"""Replacement for Makefile."""

from invoke import Collection, Context, task

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
ns.add_task(generate_doc)
