from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreGraphQLQuery

from infrahub.core.initialization import create_branch
from tests.integration.git.fingerprint_base import FingerprintImportTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


class TestFingerprintBranch(FingerprintImportTestBase):
    async def test_fingerprint_is_branch_aware(
        self, repository_id: str, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        """The branch-aware fingerprint is readable on a branch, inheriting the main value.

        Being a normal branch-aware attribute is what lets it participate in branch diffs
        and survive rebase/merge through the attribute framework.
        """
        on_main = (await client.get(kind=CoreGraphQLQuery, name__value="cartags")).fingerprint.value
        assert on_main

        await create_branch(branch_name="fingerprint-branch", db=db)

        on_branch = (
            await client.get(kind=CoreGraphQLQuery, name__value="cartags", branch="fingerprint-branch")
        ).fingerprint.value
        assert on_branch == on_main
