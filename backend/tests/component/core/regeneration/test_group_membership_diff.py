from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.regeneration.predicates import nodes_with_changed_group_membership
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

BRANCH_NAME = "change-group-membership"


class TestGroupMembershipInTheDiff(TestInfrahubApp):
    """Find the nodes that joined a group in a branch, whichever side of the membership was edited.

    A branch adds one tag to a group by editing the group, adds another by editing the tag, creates a
    third tag and renames a fourth.
    """

    @pytest.fixture(scope="class")
    async def dataset(
        self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient
    ) -> dict[str, str | list[NodeDiff]]:
        tag_ids: dict[str, str] = {}
        for name in ("added-on-the-group", "added-on-the-tag", "renamed"):
            tag = await client.create(kind=InfrahubKind.TAG, name=name)
            await tag.save()
            tag_ids[name] = tag.id
        group = await client.create(kind=InfrahubKind.STANDARDGROUP, name="generator-targets")
        await group.save()

        branch = await client.branch.create(branch_name=BRANCH_NAME, sync_with_git=False)
        branch_group = await client.get(kind=InfrahubKind.STANDARDGROUP, id=group.id, branch=branch.name)
        await branch_group.members.fetch()
        branch_group.members.add(tag_ids["added-on-the-group"])
        await branch_group.save()
        added_on_the_tag = await client.get(kind=InfrahubKind.TAG, id=tag_ids["added-on-the-tag"], branch=branch.name)
        await added_on_the_tag.add_relationships(relation_to_update="member_of_groups", related_nodes=[group.id])
        renamed = await client.get(kind=InfrahubKind.TAG, id=tag_ids["renamed"], branch=branch.name)
        renamed.name.value = "renamed-in-the-branch"
        await renamed.save()
        created = await client.create(kind=InfrahubKind.TAG, name="created", branch=branch.name)
        await created.save()

        await client.create_diff(
            branch=branch.name,
            name=BRANCH_NAME,
            from_time=datetime.fromisoformat(branch.branched_from),
            to_time=datetime.now(tz=UTC),
        )
        return {
            **tag_ids,
            "created": created.id,
            "group": group.id,
            "diff_summary": await client.get_diff_summary(branch=branch.name, name=BRANCH_NAME),
        }

    async def test_a_member_added_by_editing_the_group_records_the_change_on_the_member(
        self, dataset: dict[str, str | list[NodeDiff]]
    ) -> None:
        elements_by_node = {
            entry["id"]: {element["name"] for element in entry["elements"]} for entry in dataset["diff_summary"]
        }

        assert elements_by_node[dataset["added-on-the-group"]] == {"member_of_groups"}
        assert elements_by_node[dataset["group"]] == {"members"}

    async def test_joined_and_created_nodes_are_returned(self, dataset: dict[str, str | list[NodeDiff]]) -> None:
        node_ids = nodes_with_changed_group_membership(diff_summary=dataset["diff_summary"], query_branch=BRANCH_NAME)

        assert node_ids == {dataset["added-on-the-group"], dataset["added-on-the-tag"], dataset["created"]}
