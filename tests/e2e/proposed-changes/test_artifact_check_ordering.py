"""Artifact check ordering spans pages and stays local to each artifact definition."""

from __future__ import annotations

import re
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from helpers import Deadline, generate_random_branch_name
from infrahub_sdk.testing.repository import GitRepo
from infrahub_testcontainers.container import PROJECT_ENV_VARIABLES
from playwright.async_api import expect

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode
    from playwright.async_api import Page

pytestmark = pytest.mark.shard_foundation

REPOSITORY_FIXTURE = Path(__file__).resolve().parents[3] / "backend/tests/fixtures/repos/conflict-01/initial__main"


@dataclass(frozen=True)
class ArtifactChecks:
    title: str
    names_by_id: tuple[str, ...]

    @property
    def failed_first_names(self) -> tuple[str, ...]:
        return self.names_by_id[-2:] + self.names_by_id[:-2]


@dataclass(frozen=True)
class ProposedChangeChecks:
    proposed_change_id: str
    first: ArtifactChecks
    second: ArtifactChecks


@pytest.fixture
async def artifact_checks(
    infrahub_client: InfrahubClient,
    infrahub_compose_dir: Path,
    infrahub_provisioned_externally: bool,
) -> AsyncGenerator[ProposedChangeChecks, None]:
    if infrahub_provisioned_externally:
        pytest.skip("The fixture repository must be a directory that the containers mount")

    prefix = generate_random_branch_name("artifact-order-")
    async with AsyncExitStack() as cleanup:

        async def create_node(kind: str, **data: object) -> InfrahubNode:
            node = await infrahub_client.create(kind=kind, **data)
            await node.save()
            cleanup.push_async_callback(node.delete)
            return node

        # The source branch predates these definitions, so its automatic checks cannot replace the seeded results.
        await infrahub_client.branch.create(branch_name=prefix, sync_with_git=False)
        cleanup.push_async_callback(infrahub_client.branch.delete, branch_name=prefix)
        proposed_change = await create_node(
            "CoreProposedChange", name=prefix, source_branch=prefix, destination_branch="main"
        )

        remote_dir = infrahub_compose_dir / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]
        await GitRepo(
            name=prefix, src_directory=REPOSITORY_FIXTURE, dst_directory=remote_dir, shared=True
        ).add_to_infrahub(infrahub_client)
        repository_node = await infrahub_client.get(kind="CoreRepository", name__value=prefix)
        cleanup.push_async_callback(repository_node.delete)
        deadline = Deadline("the import of the artifact ordering fixture repository")
        while repository_node.sync_status.value != "in-sync":
            assert repository_node.sync_status.value != "error-import"
            await deadline.tick()
            repository_node = await infrahub_client.get(kind="CoreRepository", id=repository_node.id)

        query = await create_node("CoreGraphQLQuery", name=prefix, query="query { CoreAccount { count } }")
        targets = await create_node("CoreStandardGroup", name=prefix)
        transform = await create_node(
            "CoreTransformJinja2",
            name=prefix,
            query=query.id,
            repository=repository_node.id,
            template_path="unused.j2",
        )

        groups = []
        for group_index, group_name in enumerate(("A", "B")):
            definition = await create_node(
                "CoreArtifactDefinition",
                name=f"{prefix}-{group_name}",
                artifact_name="unused.txt",
                content_type="text/plain",
                parameters={},
                targets=targets.id,
                transformation=transform.id,
            )
            title = f"Artifact Validator: {prefix}-{group_name}"
            validator = await infrahub_client.create(
                kind="CoreArtifactValidator",
                label=title,
                definition=definition.id,
                proposed_change=proposed_change.id,
                state="completed",
                conclusion="failure",
                started_at=f"2026-01-01T00:00:0{group_index}Z",
                completed_at=f"2026-01-01T00:00:0{group_index + 1}Z",
            )
            await validator.save()

            check_ids = sorted(str(uuid4()) for _ in range(12))
            names = tuple(f"Check {group_name} {11 - index:02d}" for index in range(12))
            # Create in reverse UUID order, with reverse-alphabetical names, so neither is an accidental sort oracle.
            for index in reversed(range(12)):
                check = await infrahub_client.create(
                    kind="CoreArtifactCheck",
                    data={
                        "id": check_ids[index],
                        "name": names[index],
                        "label": names[index],
                        "origin": definition.id,
                        "kind": "CoreArtifactDefinition",
                        "validator": validator.id,
                        "conclusion": "failure" if index >= 10 else "success",
                        "severity": "critical" if index >= 10 else "info",
                    },
                )
                # An explicit UUID makes the SDK treat this as an existing node until create is called.
                await check.create()
            groups.append(ArtifactChecks(title=title, names_by_id=names))

        yield ProposedChangeChecks(proposed_change_id=proposed_change.id, first=groups[0], second=groups[1])


async def test_failed_first_spans_pages_and_only_resets_its_definition(
    admin_page: Page, artifact_checks: ProposedChangeChecks
) -> None:
    await admin_page.goto(f"/proposed-changes/{artifact_checks.proposed_change_id}/checks")
    first = admin_page.get_by_test_id("validator").filter(has_text=artifact_checks.first.title)
    second = admin_page.get_by_test_id("validator").filter(has_text=artifact_checks.second.title)
    titles = admin_page.get_by_text(re.compile(rf"^{re.escape(artifact_checks.first.title[:-1])}[AB]$"))
    expected_titles = [artifact_checks.first.title, artifact_checks.second.title]
    await expect(titles).to_have_text(expected_titles)
    await first.get_by_text(artifact_checks.first.title, exact=True).click()
    await second.get_by_text(artifact_checks.second.title, exact=True).click()

    first_names = first.get_by_text(re.compile(r"^Check A \d{2}$"))
    second_names = second.get_by_text(re.compile(r"^Check B \d{2}$"))
    first_sort = first.get_by_role("checkbox", name="Failed first")
    second_sort = second.get_by_role("checkbox", name="Failed first")
    await expect(first_sort).to_be_checked()
    await expect(second_sort).to_be_checked()
    await expect(first_names).to_have_text(list(artifact_checks.first.failed_first_names[:10]))
    await expect(second_names).to_have_text(list(artifact_checks.second.failed_first_names[:10]))

    await second.get_by_role("button", name="Next page", exact=True).click()
    await expect(second_names).to_have_text(list(artifact_checks.second.failed_first_names[10:]))
    await expect(first_names).to_have_text(list(artifact_checks.first.failed_first_names[:10]))
    await first.get_by_role("button", name="Next page", exact=True).click()
    await expect(first_names).to_have_text(list(artifact_checks.first.failed_first_names[10:]))

    # Toggling on page two returns only this definition to page one, in ordinary UUID order.
    await first.get_by_text("Failed first", exact=True).click()
    await expect(first_sort).not_to_be_checked()
    await expect(first_names).to_have_text(list(artifact_checks.first.names_by_id[:10]))
    await expect(second_names).to_have_text(list(artifact_checks.second.failed_first_names[10:]))
    await expect(second_sort).to_be_checked()
    await first.get_by_role("button", name="Next page", exact=True).click()
    await expect(first_names).to_have_text(list(artifact_checks.first.names_by_id[10:]))

    # These two failures normally live on page two, but enabling the sort brings both to the first page.
    await first.get_by_text("Failed first", exact=True).click()
    await expect(first_sort).to_be_checked()
    await expect(first_names).to_have_text(list(artifact_checks.first.failed_first_names[:10]))
    await expect(second_names).to_have_text(list(artifact_checks.second.failed_first_names[10:]))
    await expect(titles).to_have_text(expected_titles)
