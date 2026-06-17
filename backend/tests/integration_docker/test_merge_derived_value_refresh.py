"""A branch merge that applies a computed-attribute schema change refreshes derived values on main-only nodes."""

from __future__ import annotations

from asyncio import sleep
from copy import deepcopy
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema import AttributeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from tests.helpers.schema import WIDGET

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

KIND = WIDGET.kind


def _schema(template: str) -> dict:
    widget = deepcopy(WIDGET)
    widget.attributes.append(
        AttributeSchema(
            name="label",
            kind="Text",
            read_only=True,
            optional=True,
            computed_attribute=ComputedAttribute(kind=ComputedAttributeKind.JINJA2, jinja2_template=template),
        )
    )
    return {"version": "1.0", "nodes": [widget.model_dump()]}


async def _poll_label(client: InfrahubClient, node_id: str, expected: str, max_wait: int = 120) -> str:
    """Poll up to ``max_wait`` seconds for the node's stored label to reach ``expected``.

    The backfill is dispatched asynchronously (SchemaUpdatedEvent -> automation -> computed-attribute
    setup -> per-node update); under Redis-backed scaleout messaging that chain has non-trivial latency,
    so the budget is generous. Returns the last observed value so the caller can assert with a diagnostic.
    """
    last = ""
    for _ in range(max_wait):
        node = await client.get(kind=KIND, id=node_id)
        last = node.label.value
        if last == expected:
            return last
        await sleep(1)
    return last


class TestMergeDerivedValueRefresh(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    async def test_merge_refreshes_main_only_computed_attribute(self, client: InfrahubClient) -> None:
        # baseline: the v1 template renders the bare name
        r1 = await client.schema.load(schemas=[_schema("{{ name__value }}")], wait_until_converged=True)
        assert r1.schema_updated
        assert await client.schema.in_sync()

        alpha = await client.create(kind=KIND, data={"name": "alpha"})
        await alpha.save()
        alpha_initial = await client.get(kind=KIND, id=alpha.id)
        assert alpha_initial.label.value == "alpha"

        # sanity check: a schema-load applied directly to main (not via merge) refreshes the stored value
        rc = await client.schema.load(schemas=[_schema("v2-{{ name__value }}")], wait_until_converged=True)
        assert rc.schema_updated
        alpha_v2 = await _poll_label(client, alpha.id, expected="v2-alpha")
        assert alpha_v2 == "v2-alpha", (
            f"direct schema-load on main did not refresh the value (got {alpha_v2!r}); "
            f"without observable backfill the assertion below is inconclusive."
        )

        # load the v3 template on a branch, to be merged into main
        branch = await client.branch.create(branch_name="tmpl-v3")
        loaded = await client.schema.load(
            schemas=[_schema("v3-{{ name__value }}")], branch=branch.name, wait_until_converged=True
        )
        assert loaded.schema_updated

        # beta exists only on main (created after the branch forked), so the merge brings no data diff for it
        beta = await client.create(kind=KIND, data={"name": "beta"})
        await beta.save()
        beta_initial = await client.get(kind=KIND, id=beta.id)
        assert beta_initial.label.value == "v2-beta", f"expected main still at v2 (got {beta_initial.label.value!r})"

        merged = await client.branch.merge(branch_name=branch.name)
        assert merged

        # after the merge, main is on v3; the main-only node should refresh to "v3-beta"
        beta_after = await _poll_label(client, beta.id, expected="v3-beta")
        assert beta_after == "v3-beta", (
            f"main-only node was not refreshed after the merge (got {beta_after!r}, expected 'v3-beta')."
        )
