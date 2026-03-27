"""Replacement for Makefile."""

from invoke import Collection, Context, task

from . import backend, bundle, demo, dev, docs, main, performance, release, schema, sdk
from .utils import ESCAPED_REPO_PATH

ns = Collection()
ns.add_collection(sdk)
ns.add_collection(dev)
ns.add_collection(docs)
ns.add_collection(performance)
ns.add_collection(backend)
ns.add_collection(bundle)
ns.add_collection(demo)
ns.add_collection(main)
ns.add_collection(schema)
ns.add_collection(release)


def _collect_tasks(collection: Collection, prefix: str = "") -> list[tuple[str, str]]:
    """Recursively collect all tasks from a collection and its sub-collections."""
    tasks_info: list[tuple[str, str]] = []

    for task_name in sorted(collection.tasks):
        qualified_name = f"{prefix}.{task_name}" if prefix else task_name
        task_obj = collection.tasks[task_name]
        doc = task_obj.__doc__.strip().split("\n")[0] if task_obj.__doc__ else "No description"
        tasks_info.append((qualified_name, doc))

    for sub_name in sorted(collection.collections):
        sub_collection = collection.collections[sub_name]
        sub_prefix = f"{prefix}.{sub_name}" if prefix else sub_name
        tasks_info.extend(_collect_tasks(sub_collection, sub_prefix))

    return tasks_info


@task(name="list")
def list_tasks(_context: Context) -> None:
    """List all available invoke tasks with descriptions."""
    tasks_info = _collect_tasks(ns)
    name_width = max(len(name) for name, _ in tasks_info)

    print(f"\n  {'Task':<{name_width}}   Description")
    print(f"  {'-' * name_width}   {'-' * 50}")
    for name, desc in tasks_info:
        print(f"  {name:<{name_width}}   {desc}")
    print()


@task
def yamllint(context: Context) -> None:
    """Validate formatting of all YAML files with yamllint."""

    exec_cmd = "yamllint -s ."
    context.run(exec_cmd, pty=True)


@task(name="format")
def format_all(context: Context) -> None:
    """Run all formatters for main and backend code."""
    main.format_all(context)
    backend.format_all(context)


@task(name="lint")
def lint_all(context: Context) -> None:
    """Run all linters for YAML, main, and backend code."""
    yamllint(context)
    main.lint(context)
    backend.lint(context)


@task
def pull(context: Context) -> None:
    """Pull the latest changes from Github and update the submodule to the proper commit."""
    commands = ["git pull", "git submodule update"]
    with context.cd(ESCAPED_REPO_PATH):
        for command in commands:
            context.run(command, pty=True)


ns.add_task(list_tasks)
ns.add_task(format_all)
ns.add_task(lint_all)
ns.add_task(yamllint)
ns.add_task(pull)
