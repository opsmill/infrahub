from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from fast_depends import dependency_provider

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.exceptions import ProfileRefreshError
from infrahub.graphql.mutations.profile import InfrahubProfileMutation
from infrahub.profiles.tasks import objects_profiles_refresh_multiple, profile_refresh_process
from infrahub.workflows.catalogue import PROFILE_REFRESH_MULTIPLE
from infrahub.workflows.constants import WorkflowTag
from tests.adapters.workflow import WorkflowRecorder
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA
from tests.helpers.test_app import TestInfrahubApp
from tests.helpers.workflow_override import override_workflow

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext

DEVICE_PROFILE_KIND = f"Profile{TestKind.DEVICE}"
DEVICE_TEMPLATE_KIND = f"Template{TestKind.DEVICE}"
INTERFACE_PROFILE_KIND = f"Profile{TestKind.INTERFACE}"
SERVER_KIND = "TestingServer"
PORT_KIND = "TestingPort"

READER_SCHEMA = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Server",
            "namespace": "Testing",
            "default_filter": "name__value",
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "role", "kind": "Text", "optional": True},
            ],
        },
        {
            "name": "Port",
            "namespace": "Testing",
            "default_filter": "name__value",
            "display_label": "{{ name__value }} on {{ server__role__value }}",
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {
                    "name": "summary",
                    "kind": "Text",
                    "optional": True,
                    "read_only": True,
                    "computed_attribute": {
                        "kind": "Jinja2",
                        "jinja2_template": "{{ name__value }} uses {{ server__role__value }}",
                    },
                },
            ],
            "relationships": [{"name": "server", "peer": SERVER_KIND, "cardinality": "one", "optional": False}],
        },
    ],
}


@dataclass(frozen=True)
class ProfileDataset:
    profile_id: str
    linked_device_ids: list[str]
    unlinked_device_id: str
    template_id: str


@dataclass(frozen=True)
class ReaderDataset:
    profile_id: str
    server_id: str
    port_id: str


@dataclass(frozen=True)
class InterfaceProfileDataset:
    profile_id: str
    linked_interface_ids: list[str]
    template_id: str


class TestProfileRefreshBatching(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def context(self, db: InfrahubDatabase, initialize_registry: None, default_branch: Branch) -> EventContext:
        admin_account = await NodeManager.get_one_by_hfid(
            db=db, kind=InfrahubKind.ACCOUNT, hfid=["admin"], raise_on_error=True
        )
        return InfrahubContext(
            account=AccountSession(authenticated=True, account_id=admin_account.id, auth_type=AuthType.API),
            branch=BranchContext(name=default_branch.name, id=str(default_branch.uuid)),
        ).to_event_context()

    @pytest.fixture(scope="class")
    async def load_schema(self, client: InfrahubClient, default_branch: Branch) -> None:
        device_schema = DEVICE_SCHEMA.model_dump()
        device_schema["version"] = "1.0"
        response = await client.schema.load(schemas=[device_schema])
        assert not response.errors

    @pytest.fixture(scope="class")
    async def reader_dataset(self, client: InfrahubClient, load_schema: None) -> ReaderDataset:
        response = await client.schema.load(schemas=[READER_SCHEMA])
        assert not response.errors
        profile = await client.create(
            kind=f"Profile{SERVER_KIND}", profile_name="server-profile", profile_priority=1000, role="role-1"
        )
        await profile.save()
        server = await client.create(kind=SERVER_KIND, name="server-1", profiles=[profile.id])
        await server.save()
        port = await client.create(kind=PORT_KIND, name="port-1", server=server.id)
        await port.save()
        return ReaderDataset(profile_id=profile.id, server_id=server.id, port_id=port.id)

    async def _port_readers(self, db: InfrahubDatabase, port_id: str) -> tuple[str, str | None]:
        port = await NodeManager.get_one(db=db, id=port_id, raise_on_error=True)
        return await port.get_display_label(db=db), port.get_attribute(name="summary").value

    @pytest.fixture(scope="class")
    async def dataset(self, client: InfrahubClient, load_schema: None) -> ProfileDataset:
        profile = await client.create(
            kind=DEVICE_PROFILE_KIND, profile_name="device-profile", profile_priority=1000, part_number="part-1"
        )
        await profile.save()

        devices = []
        for idx, profiles in enumerate([[profile.id], [profile.id], [profile.id], []]):
            device = await client.create(
                kind=TestKind.DEVICE,
                name=f"device-{idx}",
                manufacturer="manufacturer",
                weight=1,
                airflow="Front to rear",
                profiles=profiles,
            )
            await device.save()
            devices.append(device)

        template = await client.create(
            kind=DEVICE_TEMPLATE_KIND, template_name="device-template", profiles=[profile.id]
        )
        await template.save()

        return ProfileDataset(
            profile_id=profile.id,
            linked_device_ids=[device.id for device in devices[:3]],
            unlinked_device_id=devices[3].id,
            template_id=template.id,
        )

    @pytest.fixture(scope="class")
    async def interface_dataset(self, client: InfrahubClient, load_schema: None) -> InterfaceProfileDataset:
        profile = await client.create(
            kind=INTERFACE_PROFILE_KIND, profile_name="interface-profile", profile_priority=1000, enabled=False
        )
        await profile.save()
        device = await client.create(
            kind=TestKind.DEVICE, name="interface-device", manufacturer="manufacturer", weight=1, airflow="Passive"
        )
        await device.save()

        interfaces = []
        for idx, (kind, profiles) in enumerate(
            [
                (TestKind.VIRTUAL_INTERFACE, [profile.id]),
                (TestKind.PHYSICAL_INTERFACE, [profile.id]),
                (TestKind.VIRTUAL_INTERFACE, [profile.id]),
                (TestKind.VIRTUAL_INTERFACE, []),
            ]
        ):
            extra = {"phys_type": "SFP (1GE)"} if kind == TestKind.PHYSICAL_INTERFACE else {}
            interface = await client.create(
                kind=kind, name=f"interface-{idx}", device=device.id, profiles=profiles, **extra
            )
            await interface.save()
            interfaces.append(interface)

        device_template = await client.create(kind=DEVICE_TEMPLATE_KIND, template_name="interface-device-template")
        await device_template.save()
        template = await client.create(
            kind=f"Template{TestKind.VIRTUAL_INTERFACE}",
            template_name="interface-template",
            name="interface-template",
            device=device_template.id,
            profiles=[profile.id],
        )
        await template.save()

        return InterfaceProfileDataset(
            profile_id=profile.id,
            linked_interface_ids=[interface.id for interface in interfaces[:3]],
            template_id=template.id,
        )

    async def _set_profile_part_number(self, client: InfrahubClient, profile_id: str, part_number: str) -> None:
        profile = await client.get(kind=DEVICE_PROFILE_KIND, id=profile_id)
        profile.part_number.value = part_number
        await profile.save()

    async def _part_numbers(self, client: InfrahubClient, kind: str, node_ids: list[str]) -> list[str | None]:
        return [(await client.get(kind=kind, id=node_id)).part_number.value for node_id in node_ids]

    async def test_profile_refresh_submits_one_flow_per_chunk_of_linked_nodes_then_templates(
        self,
        dataset: ProfileDataset,
        default_branch: Branch,
        client: InfrahubClient,
        context: EventContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The refresh reads the linked node and template ids in pages and submits one flow per chunk.

        The device with no profile is never submitted, and each run links to the profile, not to each node.
        """
        # Limit 4 -> chunk size 2, so the three linked devices split into [2, 1].
        monkeypatch.setenv("PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES", "4")
        # The default pagination size would return all three ids in one page, leaving paging between chunks untested.
        monkeypatch.setattr(client.config, "pagination_size", 2)

        recorder = WorkflowRecorder()
        with override_workflow(recorder, dependency_provider=dependency_provider):
            await profile_refresh_process(
                branch_name=default_branch.name,
                profile_kind=DEVICE_PROFILE_KIND,
                profile_id=dataset.profile_id,
                context=context,
            )

        submissions = recorder.get_submit_calls_for(PROFILE_REFRESH_MULTIPLE)
        assert len(recorder.submit_calls) == len(submissions)
        assert [len(call["parameters"]["node_ids"]) for call in submissions] == [2, 1, 1]
        device_chunk_ids = [node_id for call in submissions[:2] for node_id in call["parameters"]["node_ids"]]
        assert sorted(device_chunk_ids) == sorted(dataset.linked_device_ids)
        assert submissions[2]["parameters"]["node_ids"] == [dataset.template_id]
        assert [call["parameters"]["branch_name"] for call in submissions] == [default_branch.name] * 3
        assert [call["parameters"]["context"] for call in submissions] == [context] * 3
        assert [call["context"] for call in submissions] == [context] * 3
        assert [call["tags"] for call in submissions] == [
            [
                WorkflowTag.BRANCH.render(identifier=default_branch.name),
                WorkflowTag.RELATED_NODE.render(identifier=dataset.profile_id),
            ]
        ] * 3

    async def test_profile_refresh_reads_the_peers_of_a_generic_profile(
        self,
        interface_dataset: InterfaceProfileDataset,
        default_branch: Branch,
        client: InfrahubClient,
        context: EventContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A profile of a generic reads its linked nodes and templates of every concrete kind through the generics."""
        monkeypatch.setenv("PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES", "4")
        monkeypatch.setattr(client.config, "pagination_size", 2)

        recorder = WorkflowRecorder()
        with override_workflow(recorder, dependency_provider=dependency_provider):
            await profile_refresh_process(
                branch_name=default_branch.name,
                profile_kind=INTERFACE_PROFILE_KIND,
                profile_id=interface_dataset.profile_id,
                context=context,
            )

        submissions = recorder.get_submit_calls_for(PROFILE_REFRESH_MULTIPLE)
        assert [len(call["parameters"]["node_ids"]) for call in submissions] == [2, 1, 1]
        interface_chunk_ids = [node_id for call in submissions[:2] for node_id in call["parameters"]["node_ids"]]
        assert sorted(interface_chunk_ids) == sorted(interface_dataset.linked_interface_ids)
        assert submissions[2]["parameters"]["node_ids"] == [interface_dataset.template_id]

    async def test_send_profile_refresh_workflows_submits_one_flow_per_chunk(
        self,
        db: InfrahubDatabase,
        dataset: ProfileDataset,
        default_branch: Branch,
        context: EventContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES", "4")
        node_ids = [*dataset.linked_device_ids, dataset.unlinked_device_id, dataset.template_id]
        profile = await NodeManager.get_one(db=db, id=dataset.profile_id, raise_on_error=True)

        recorder = WorkflowRecorder()
        await InfrahubProfileMutation._send_profile_refresh_workflows(
            db=db,
            workflow_service=recorder,
            branch_name=default_branch.name,
            obj=profile,
            context=context,
            node_ids=node_ids,
        )

        submissions = recorder.get_submit_calls_for(PROFILE_REFRESH_MULTIPLE)
        assert [call["parameters"]["node_ids"] for call in submissions] == [node_ids[0:2], node_ids[2:4], node_ids[4:]]
        assert [call["parameters"]["context"] for call in submissions] == [context] * 3
        assert [call["context"] for call in submissions] == [context] * 3
        assert [call["tags"] for call in submissions] == [
            [
                WorkflowTag.BRANCH.render(identifier=default_branch.name),
                WorkflowTag.RELATED_NODE.render(identifier=dataset.profile_id),
            ]
        ] * 3

    async def test_profile_attribute_change_reaches_the_linked_template(
        self, dataset: ProfileDataset, default_branch: Branch, client: InfrahubClient, context: EventContext
    ) -> None:
        await self._set_profile_part_number(client=client, profile_id=dataset.profile_id, part_number="part-2")

        await profile_refresh_process(
            branch_name=default_branch.name,
            profile_kind=DEVICE_PROFILE_KIND,
            profile_id=dataset.profile_id,
            context=context,
        )

        assert await self._part_numbers(client=client, kind=DEVICE_TEMPLATE_KIND, node_ids=[dataset.template_id]) == [
            "part-2"
        ]
        assert await self._part_numbers(
            client=client, kind=TestKind.DEVICE, node_ids=[*dataset.linked_device_ids, dataset.unlinked_device_id]
        ) == ["part-2", "part-2", "part-2", None]

    async def test_chunk_refresh_applies_the_other_nodes_and_raises_for_a_deleted_node(
        self, dataset: ProfileDataset, default_branch: Branch, client: InfrahubClient, context: EventContext
    ) -> None:
        deleted_device = await client.create(
            kind=TestKind.DEVICE,
            name="device-deleted",
            manufacturer="manufacturer",
            weight=1,
            airflow="Front to rear",
            profiles=[dataset.profile_id],
        )
        await deleted_device.save()
        await deleted_device.delete()
        await self._set_profile_part_number(client=client, profile_id=dataset.profile_id, part_number="part-3")
        refreshed_ids = dataset.linked_device_ids[:2]

        with pytest.raises(
            ProfileRefreshError, match=rf"^The profile refresh failed for 1 node\(s\): {deleted_device.id}$"
        ):
            await objects_profiles_refresh_multiple(
                branch_name=default_branch.name,
                node_ids=[refreshed_ids[0], deleted_device.id, refreshed_ids[1]],
                context=context,
            )

        assert await self._part_numbers(client=client, kind=TestKind.DEVICE, node_ids=refreshed_ids) == [
            "part-3",
            "part-3",
        ]

    async def test_profile_attribute_change_recomputes_the_readers_on_other_nodes(
        self,
        db: InfrahubDatabase,
        reader_dataset: ReaderDataset,
        default_branch: Branch,
        client: InfrahubClient,
        context: EventContext,
    ) -> None:
        """The display label and the computed attribute of a port read the role that a profile sets on its server."""
        assert await self._port_readers(db=db, port_id=reader_dataset.port_id) == (
            "port-1 on role-1",
            "port-1 uses role-1",
        )
        profile = await client.get(kind=f"Profile{SERVER_KIND}", id=reader_dataset.profile_id)
        profile.role.value = "role-2"
        await profile.save()

        await profile_refresh_process(
            branch_name=default_branch.name,
            profile_kind=f"Profile{SERVER_KIND}",
            profile_id=reader_dataset.profile_id,
            context=context,
        )

        server = await client.get(kind=SERVER_KIND, id=reader_dataset.server_id)
        assert server.role.value == "role-2"
        assert await self._port_readers(db=db, port_id=reader_dataset.port_id) == (
            "port-1 on role-2",
            "port-1 uses role-2",
        )
