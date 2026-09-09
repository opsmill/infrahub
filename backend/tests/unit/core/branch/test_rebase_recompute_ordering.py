"""When the post-rebase pass builds its resolver.

A rebase stamps its replayed node events with the ``rebase`` origin, which is what stops the
per-node Python automations from answering them. The coalesced pass is then the only thing that
refreshes those values, so whatever the pass needs has to be in hand before those events go out.
Building the resolver afterwards leaves a failure there with the changes suppressed and nothing
recomputing them.

The merge path builds its resolver while the orchestrator is assembled, before any merge work. This
asserts the rebase path keeps the same order, by reading the source.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

from infrahub.core.branch import tasks

BUILD_RESOLVER = "build_python_target_resolver"
SEND_EVENT = "send"


def _positions(name: str, body: ast.AST) -> list[int]:
    found = []
    for node in ast.walk(body):
        if isinstance(node, ast.Call):
            func = node.func
            called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if called == name:
                found.append(node.lineno)
    return sorted(found)


def test_the_resolver_is_built_before_the_suppressed_events_are_sent() -> None:
    source = textwrap.dedent(inspect.getsource(tasks.rebase_branch.fn))
    parsed = ast.parse(source)

    builds = _positions(BUILD_RESOLVER, parsed)
    sends = _positions(SEND_EVENT, parsed)

    assert len(builds) == 1, "the rebase path builds the Python target resolver exactly once"
    assert sends, "the rebase path sends its replayed events"
    assert builds[0] < min(sends), (
        "the resolver is built after the rebase-origin events go out, so a failure building it "
        "leaves the replayed changes suppressed with no coalesced pass behind them"
    )
