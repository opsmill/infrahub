from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator

import pytest
from infrahub_sdk.protocols import CoreTransformPython
from prefect.client.orchestration import PrefectClient, get_client

from infrahub.core.constants import InfrahubKind
from infrahub.events.constants import NODE_ORIGIN_LABEL, NodeMutationOrigin
from infrahub.events.node_action import NodeUpdatedEvent
from tests.helpers.constants import PREFECT_EVENT_WAIT_SECONDS
from tests.helpers.events import query_events_by_name
from tests.integration.git.fingerprint_base import FingerprintImportTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from prefect.events.schemas.events import Event

    from tests.helpers.file_repo import FileRepo


class TestSelectiveRecompute(FingerprintImportTestBase):
    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect: str) -> AsyncGenerator[PrefectClient, None]:
        # `prefect` sets PREFECT_API_URL to the same server the import flow publishes events to,
        # so the client reads the events a real import actually emitted.
        async with get_client(sync_client=False) as client:
            yield client

    async def test_source_edit_then_revert_restores_original_fingerprint(
        self, repository_id: str, client: InfrahubClient, file_repo: FileRepo
    ) -> None:
        """A faithful content revert restores a watch-declared transform's fingerprint bit for bit.

        A transform that declares a non-empty watch has a stable, content-derived fingerprint: the
        commit id is not folded in, so identical content always yields an identical fingerprint. An
        edit changes it and a revert to the original bytes restores the exact original value across
        forward commits. An unchanged fingerprint emits no update event, so the revert triggers no
        recompute.
        """
        transform_path = "transforms/car_spec_markdown.py"
        manifest_path = ".infrahub.yml"
        original_transform_source = (Path(file_repo.path) / transform_path).read_text(encoding="utf-8")

        # Give CarSpecMarkdown a non-empty watch so its fingerprint stops folding in the commit id.
        # The watch block is inserted under the existing entry; the rest of the manifest is preserved
        # exactly so no other definition changes.
        original_manifest = (Path(file_repo.path) / manifest_path).read_text(encoding="utf-8")
        car_spec_entry = (
            "  - name: CarSpecMarkdown\n"
            "    class_name: CarSpecMarkdown\n"
            '    file_path: "transforms/car_spec_markdown.py"\n'
        )
        assert car_spec_entry in original_manifest
        watched_entry = car_spec_entry + "    watch:\n      files:\n        - " + f'"{transform_path}"\n'
        watched_manifest = original_manifest.replace(car_spec_entry, watched_entry)
        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={manifest_path: watched_manifest},
        )

        stable_fingerprint = (
            await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")
        ).fingerprint.value

        # An unrelated commit outside the transform's closure must not move the fingerprint now that
        # the watch pins the closure and the commit id is no longer folded in.
        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={"README_unrelated.md": "an unrelated file outside the transform closure\n"},
        )
        after_unrelated_fingerprint = (
            await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")
        ).fingerprint.value
        assert after_unrelated_fingerprint == stable_fingerprint

        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={transform_path: original_transform_source + "\n# fingerprint change marker\n"},
        )
        edited_fingerprint = (
            await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")
        ).fingerprint.value
        assert edited_fingerprint != stable_fingerprint

        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={transform_path: original_transform_source},
        )
        reverted_fingerprint = (
            await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")
        ).fingerprint.value
        assert reverted_fingerprint == stable_fingerprint

        # Restore the manifest to its watch-free shape so the class-scoped source repo returns to the
        # no-watch state the other scenarios in this class assume.
        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={manifest_path: original_manifest},
        )

    async def test_unrelated_commit_changes_fingerprint_without_watch(
        self, repository_id: str, client: InfrahubClient, file_repo: FileRepo
    ) -> None:
        """A commit outside a transform's closure still churns its fingerprint when no watch is declared.

        No python transform in this fixture declares a `watch`, so the commit id is folded into every
        fingerprint. Any commit, even one touching an unrelated file, therefore changes the fingerprint,
        which is the safe over-regenerating per-commit default. The watch-declared-stable case (a watch
        pins the closure and drops the commit id, leaving the fingerprint stable across unrelated
        commits) is covered by the fingerprint foundation suite.
        """
        before = (await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")).fingerprint.value

        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={"README_unrelated.md": "an unrelated file outside every transform closure\n"},
        )

        after = (await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")).fingerprint.value
        assert after != before

    async def test_reimport_same_commit_leaves_every_transform_fingerprint_unchanged(
        self, repository_id: str, client: InfrahubClient
    ) -> None:
        """Re-importing the same commit is idempotent for every transform's fingerprint.

        A recompute is gated on a changed fingerprint; a no-op re-import must not churn any of them.
        """
        before = {
            transform.name.value: transform.fingerprint.value
            for transform in await client.all(kind=CoreTransformPython)
        }
        assert before

        await self._reimport_current_commit(client=client, repository_id=repository_id)

        after = {
            transform.name.value: transform.fingerprint.value
            for transform in await client.all(kind=CoreTransformPython)
        }
        assert after == before

    async def test_null_fingerprint_self_heals_to_a_stable_value(
        self, repository_id: str, client: InfrahubClient
    ) -> None:
        """A transform carrying a null fingerprint is stamped to a stable value on the next import.

        A pre-feature transform has no stored fingerprint. The first import after the feature lands
        computes and stores one (the null->value transition is the update event that self-heals the
        recompute gate); a subsequent no-change import leaves it untouched, so the heal is bounded to
        a single pass.
        """
        transform = await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")
        transform.fingerprint.value = None
        await transform.save()

        assert (await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")).fingerprint.value is None

        await self._reimport_current_commit(client=client, repository_id=repository_id)
        healed = (await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")).fingerprint.value
        assert healed is not None

        await self._reimport_current_commit(client=client, repository_id=repository_id)
        after_second = (await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")).fingerprint.value
        assert after_second == healed

    async def test_import_emits_fingerprint_update_event_for_transform(
        self, repository_id: str, client: InfrahubClient, file_repo: FileRepo, prefect_client: PrefectClient
    ) -> None:
        """A real import that changes a transform's fingerprint emits the node event the trigger matches.

        The update trigger keys on a node.updated event whose primary node is the transform and whose
        related resources carry a fingerprint attribute update. This proves the import produces exactly
        that event, tagged as a live edit.
        """
        transform = await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")
        transform_id = transform.id

        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={
                "transforms/car_spec_markdown.py": (Path(file_repo.path) / "transforms/car_spec_markdown.py").read_text(
                    encoding="utf-8"
                )
                + "\n# event linkage marker\n"
            },
        )

        matching_event = await self._wait_for_fingerprint_update_event(
            prefect_client=prefect_client, transform_id=transform_id
        )
        assert matching_event is not None, "no node.updated event with a fingerprint attribute update for the transform"
        assert matching_event.resource["infrahub.node.kind"] == InfrahubKind.TRANSFORMPYTHON
        assert matching_event.resource[NODE_ORIGIN_LABEL] == NodeMutationOrigin.LIVE.value

    async def _wait_for_fingerprint_update_event(
        self, prefect_client: PrefectClient, transform_id: str
    ) -> Event | None:
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            events = await query_events_by_name(client=prefect_client, event_name=NodeUpdatedEvent.event_name)
            for event in events:
                if event.resource.get("infrahub.node.id") != transform_id:
                    continue
                if any(
                    related.role == "infrahub.node.attribute_update"
                    and related.get("infrahub.field.name") == "fingerprint"
                    for related in event.related
                ):
                    return event
            await asyncio.sleep(1)
        return None
