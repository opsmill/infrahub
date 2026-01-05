from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.test_app import TestInfrahubApp

from infrahub.core.constants.infrahubkind import CHANGECOMMENT, CHANGETHREAD, PROPOSEDCHANGE, THREADCOMMENT
from infrahub.core.initialization import create_branch

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestProposedChangeTotalComments(TestInfrahubApp):
    async def test_get_total_comments(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        car_person_schema: SchemaBranch,
        unprivileged_client: InfrahubClient,
    ) -> None:
        """
        Creates both change comments and thread-attached comments and make sur `total_comments` property
        is computed correctly.
        """

        # Create a branch for the proposed change
        source_branch = await create_branch(branch_name="branch-proposed-change", db=db)

        # Create a proposed change
        proposed_change = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": source_branch.name, "destination_branch": "main", "name": "test-pc"},
        )
        await proposed_change.save()

        # Create a global comment
        pc_comment = await client.create(
            kind=CHANGECOMMENT,
            data={"change": proposed_change.id, "text": "A global comment"},
        )
        await pc_comment.save()

        # Create a global thread
        pc_thread = await client.create(
            kind=CHANGETHREAD,
            data={"change": proposed_change.id},
        )
        await pc_thread.save()

        # Create comments on these threads
        pc_thread_comment_1 = await client.create(
            kind=THREADCOMMENT,
            data={"thread": pc_thread.id, "text": "A thread comment"},
        )
        await pc_thread_comment_1.save()
        pc_thread_comment_2 = await client.create(
            kind=THREADCOMMENT,
            data={"thread": pc_thread.id, "text": "A thread comment"},
        )
        await pc_thread_comment_2.save()

        query: str = """
            query ($ids: [ID]!){
              CoreProposedChange(ids: $ids)  {
                count
                edges {
                  node {
                    total_comments { value }
                  }
                }
              }
            }
        """

        result = await client.execute_graphql(query=query, variables={"ids": [proposed_change.id]})
        assert result["CoreProposedChange"]["edges"][0]["node"]["total_comments"]["value"] == 3

    async def test_no_comments(
        self,
        client: InfrahubClient,
        db: InfrahubDatabase,
        car_person_schema: SchemaBranch,
        unprivileged_client: InfrahubClient,
    ) -> None:
        """
        Creates both change comments and thread-attached comments and make sur `total_comments` property
        is computed correctly.
        """

        # Create a branch for the proposed change
        source_branch = await create_branch(branch_name="branch-proposed-change", db=db)

        # Create a proposed change
        proposed_change = await client.create(
            kind=PROPOSEDCHANGE,
            data={"source_branch": source_branch.name, "destination_branch": "main", "name": "test-pc"},
        )
        await proposed_change.save()

        query: str = """
            query ($ids: [ID]!){
              CoreProposedChange(ids: $ids)  {
                count
                edges {
                  node {
                    total_comments { value }
                  }
                }
              }
            }
        """

        result = await client.execute_graphql(query=query, variables={"ids": [proposed_change.id]})
        assert result["CoreProposedChange"]["edges"][0]["node"]["total_comments"]["value"] == 0
