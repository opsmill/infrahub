from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import uvicorn
import yaml
from infrahub_sdk.protocols import (
    CoreArtifact,
    CoreArtifactCheck,
    CoreArtifactDefinition,
    CoreArtifactValidator,
    CoreProposedChange,
    CoreReadOnlyRepository,
    CoreStandardWebhook,
)
from prefect.client.orchestration import get_client as get_prefect_client

from infrahub import config
from infrahub.core.constants import (
    ArtifactStatus,
    EventType,
    InfrahubKind,
    ValidatorConclusion,
    ValidatorState,
)
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.server import app
from infrahub.workflows.catalogue import WEBHOOK_PROCESS
from tests.constants import TestKind
from tests.helpers.constants import PREFECT_EVENT_WAIT_SECONDS
from tests.helpers.events import query_events_by_name
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import load_schema
from tests.helpers.schema.device import DEVICE, INTERFACE, INTERFACE_HOLDER, VIRTUAL_INTERFACE
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Iterator

    from infrahub_sdk import InfrahubClient
    from prefect.client.orchestration import PrefectClient
    from prefect.events.schemas.events import Event

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from tests.helpers.test_client import InfrahubTestClient

REPOSITORY_NAME = "external-render"
BRANCH_NAME = "change-123"
DEFINITION_NAME = "startup-config"
RENDER_TOKEN_HEADER = "X-Infrahub-Render-Token"
RENDER_TIMEOUT_SECONDS = 60
LOOPBACK = "127.0.0.1"

ARTIFACT_TARGET_DEVICE = deepcopy(DEVICE)
ARTIFACT_TARGET_DEVICE.inherit_from = [*DEVICE.inherit_from, InfrahubKind.ARTIFACTTARGET]
ARTIFACT_TARGET_DEVICE.display_label = "name__value"
DESCRIBED_INTERFACE = deepcopy(INTERFACE)
DESCRIBED_INTERFACE.attributes.append(AttributeSchema(name="description", kind="Text", optional=True))
EDGE_ROUTER_SCHEMA = SchemaRoot(
    generics=[DESCRIBED_INTERFACE, INTERFACE_HOLDER], nodes=[ARTIFACT_TARGET_DEVICE, VIRTUAL_INTERFACE]
)

DEVICE_CONFIG_QUERY = """
query device_config($name: String!) {
  TestingDevice(name__value: $name) {
    edges {
      node {
        name { value }
        interfaces {
          edges {
            node {
              name { value }
              description { value }
            }
          }
        }
      }
    }
  }
}
"""


def _repository_config(version: str) -> dict[str, Any]:
    return {
        "queries": [{"name": "device_config", "file_path": "queries/device_config.gql"}],
        "external_transforms": [
            {"name": "ansible-startup-config", "query": "device_config", "version": version, "timeout": 600}
        ],
        "artifact_definitions": [
            {
                "name": DEFINITION_NAME,
                "artifact_name": DEFINITION_NAME,
                "parameters": {"name": "name__value"},
                "content_type": "text/plain",
                "targets": "edge-routers",
                "transformation": "ansible-startup-config",
            }
        ],
    }


QUERY_RENDER_REQUESTED_EVENTS = """
query($artifact_ids: [String!]) {
  InfrahubEvent(event_type: ["infrahub.artifact.render_requested"], primary_node__ids: $artifact_ids, limit: 50) {
    edges { node { id event ... on StandardEvent { payload } } }
  }
}
"""
QUERY_WEBHOOK_TASKS = """
query($webhook_id: String!) {
  InfrahubTask(related_node__ids: [$webhook_id]) {
    count
    edges {
      node {
        workflow
        parameters
        ... on WebhookDeliveryTask {
          http_request { url headers }
          http_response { status_code body }
        }
      }
    }
  }
}
"""


@dataclass
class ReceivedRequest:
    token: str
    data: dict[str, Any]
    callback_status: int | None = None


@dataclass
class ReferenceEngine:
    """A render engine that speaks only plain HTTP and JSON, as a customer's own engine would."""

    received: list[ReceivedRequest] = field(default_factory=list)
    server: ThreadingHTTPServer | None = None

    @property
    def url(self) -> str:
        assert self.server is not None
        return f"http://{LOOPBACK}:{self.server.server_port}/render"

    def start(self) -> None:
        engine = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                request = ReceivedRequest(token=self.headers[RENDER_TOKEN_HEADER], data=body["data"])
                engine.received.append(request)
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self.end_headers()
                # The reply goes out after the delivery is acknowledged, as an engine running a job would.
                threading.Thread(target=engine.call_back, args=(request,), daemon=True).start()

            def log_message(self, format: str, *args: Any) -> None:
                return

        self.server = ThreadingHTTPServer((LOOPBACK, 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()

    @staticmethod
    def render(query_result: dict[str, Any]) -> str:
        device = query_result["TestingDevice"]["edges"][0]["node"]
        lines = [f"hostname {device['name']['value']}"]
        interfaces = sorted(device["interfaces"]["edges"], key=lambda edge: edge["node"]["name"]["value"])
        for interface in interfaces:
            lines.extend(
                [
                    f"interface {interface['node']['name']['value']}",
                    f" description {interface['node']['description']['value']}",
                ]
            )
        return "\n".join(lines) + "\n"

    def call_back(self, request: ReceivedRequest) -> None:
        body = json.dumps(
            {
                "status": "success",
                "content": self.render(request.data["query_result"]),
                "content_type": request.data["content_type"],
            }
        ).encode()
        while True:
            # The callback URL is the http URL Infrahub built from main.public_url.
            callback = urllib.request.Request(  # noqa: S310
                request.data["callback_url"],
                data=body,
                method="POST",
                headers={"Content-Type": "application/json", RENDER_TOKEN_HEADER: request.token},
            )
            try:
                with urllib.request.urlopen(callback, timeout=RENDER_TIMEOUT_SECONDS) as response:  # noqa: S310
                    request.callback_status = response.status
                    return
            except urllib.error.HTTPError as error:
                if error.code != 429:
                    request.callback_status = error.code
                    return
                time.sleep(float(error.headers.get("Retry-After", "1")))


class RunLogRecorder(logging.Handler):
    """Keeps the flow-run log lines, which the test Prefect server does not receive from in-process runs."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


class _InProcessServer(uvicorn.Server):
    """Serves the API under test on a real socket so the engine can reach the callback URL over HTTP."""

    def capture_signals(self) -> Any:
        return nullcontext()


def _expected_config(name: str, descriptions: dict[str, str]) -> str:
    lines = [f"hostname {name}"]
    for interface, description in sorted(descriptions.items()):
        lines += [f"interface {interface}", f" description {description}"]
    return "\n".join(lines) + "\n"


class TestExternalArtifact(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def run_logs(self) -> Iterator[RunLogRecorder]:
        recorder = RunLogRecorder()
        logger = logging.getLogger("prefect.flow_runs")
        original_level = logger.level
        logger.setLevel(logging.INFO)
        logger.addHandler(recorder)
        yield recorder
        logger.removeHandler(recorder)
        logger.setLevel(original_level)

    @pytest.fixture(scope="class")
    def engine(self) -> Iterator[ReferenceEngine]:
        engine = ReferenceEngine()
        engine.start()
        yield engine
        engine.stop()

    @pytest.fixture(scope="class")
    async def public_url(self, test_client: InfrahubTestClient) -> AsyncGenerator[str, None]:
        listener = socket.socket()
        listener.bind((LOOPBACK, 0))
        server = _InProcessServer(uvicorn.Config(app=app, lifespan="off", log_level="warning"))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        for _ in range(RENDER_TIMEOUT_SECONDS * 20):
            if server.started:
                break
            await asyncio.sleep(0.05)
        assert server.started
        host, port = listener.getsockname()
        original = config.SETTINGS.main.public_url
        config.SETTINGS.main.public_url = f"http://{host}:{port}"
        yield config.SETTINGS.main.public_url
        config.SETTINGS.main.public_url = original
        server.should_exit = True
        await serving

    @pytest.fixture(scope="class")
    def selective_execution_after_merge(self) -> Generator[None, None, None]:
        original = config.SETTINGS.main.selective_execution_after_merge
        config.SETTINGS.main.selective_execution_after_merge = True
        yield
        config.SETTINGS.main.selective_execution_after_merge = original

    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect: str) -> AsyncGenerator[PrefectClient, None]:
        async with get_prefect_client(sync_client=False) as client:
            yield client

    @pytest.fixture(scope="class")
    def file_repo(self, git_repos_source_dir_module_scope: Path) -> FileRepo:
        file_repo = FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        query_path = Path(file_repo.path) / "queries" / "device_config.gql"
        query_path.parent.mkdir(parents=True, exist_ok=True)
        query_path.write_text(DEVICE_CONFIG_QUERY, encoding="utf-8")
        (Path(file_repo.path) / ".infrahub.yml").write_text(
            yaml.safe_dump(_repository_config(version="1.5.0")), encoding="utf-8"
        )
        file_repo.repo.git.add(".")
        file_repo.repo.index.commit("add external transformation")
        return file_repo

    @pytest.fixture(scope="class")
    async def webhook_id(
        self, db: InfrahubDatabase, initialize_registry: None, client: InfrahubClient, engine: ReferenceEngine
    ) -> str:
        await load_schema(db, schema=EDGE_ROUTER_SCHEMA)
        webhook = await client.create(
            kind=CoreStandardWebhook,
            name="reference-engine",
            url=engine.url,
            event_type=EventType.ARTIFACT_RENDER_REQUESTED.value,
            branch_scope="all_branches",
            shared_key="reference-engine-shared-key",
            validate_certificates=False,
        )
        await webhook.save()
        return webhook.id

    @pytest.fixture(scope="class")
    async def edge_routers(self, db: InfrahubDatabase, webhook_id: str) -> dict[str, str]:
        devices = []
        for name in ("edge-01", "edge-02", "edge-03"):
            device = await Node.init(schema=TestKind.DEVICE, db=db)
            await device.new(db=db, name=name, manufacturer="Juniper", weight=10, airflow="Front to rear")
            await device.save(db=db)
            interface = await Node.init(schema=TestKind.VIRTUAL_INTERFACE, db=db)
            await interface.new(db=db, name="ge-0/0/0", description="uplink", device=device)
            await interface.save(db=db)
            devices.append(device)
        group = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await group.new(db=db, name="edge-routers", members=devices)
        await group.save(db=db)
        return {device.name.value: device.id for device in devices}  # type: ignore[attr-defined]

    @pytest.fixture(scope="class")
    async def definition_id(
        self,
        edge_routers: dict[str, str],
        file_repo: FileRepo,
        client: InfrahubClient,
        public_url: str,
        selective_execution_after_merge: None,
    ) -> str:
        """Importing the repository creates the definition, which requests a render of every target on main."""
        repository = await client.create(
            kind=CoreReadOnlyRepository, name=REPOSITORY_NAME, location=file_repo.path, ref="main"
        )
        await repository.save()
        definition = await client.get(kind=CoreArtifactDefinition, name__value=DEFINITION_NAME)
        return definition.id

    async def _artifact(self, client: InfrahubClient, device_id: str, branch: str) -> CoreArtifact:
        artifacts = await client.filters(kind=CoreArtifact, object__ids=[device_id], branch=branch)
        assert len(artifacts) == 1
        return artifacts[0]

    async def _render_requests(
        self, prefect_client: PrefectClient, artifact_id: str, branch: str, count: int
    ) -> list[Event]:
        """Wait for `count` render requests of the artifact on the branch to reach the event store and return them."""
        events: list[Event] = []
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            events = [
                event
                for event in await query_events_by_name(
                    client=prefect_client,
                    event_name=EventType.ARTIFACT_RENDER_REQUESTED.value,
                    resource_id=artifact_id,
                )
                if event.payload["data"]["branch"] == branch
            ]
            if len(events) >= count:
                break
            await asyncio.sleep(1)
        return sorted(events, key=lambda event: event.occurred)

    async def _deliver(self, service: InfrahubServices, webhook_id: str, event: Event) -> None:
        """Run the webhook delivery with the parameters the webhook automation renders from the event."""
        await service.workflow.execute_workflow(
            workflow=WEBHOOK_PROCESS,
            parameters={
                "webhook_id": webhook_id,
                "webhook_name": "reference-engine",
                "webhook_kind": InfrahubKind.STANDARDWEBHOOK,
                "branch_name": event.resource["infrahub.branch.name"],
                "event_id": str(event.id),
                "event_type": event.event,
                "event_occured_at": event.occurred.isoformat(),
                "event_payload": event.payload,
            },
        )

    async def _wait_until_ready(self, client: InfrahubClient, artifact_id: str, branch: str) -> CoreArtifact:
        artifact = await client.get(kind=CoreArtifact, id=artifact_id, branch=branch)
        for _ in range(RENDER_TIMEOUT_SECONDS * 10):
            if artifact.status.value == ArtifactStatus.READY.value:
                return artifact
            await asyncio.sleep(0.1)
            artifact = await client.get(kind=CoreArtifact, id=artifact_id, branch=branch)
        pytest.fail(f"artifact {artifact_id} on {branch} is {artifact.status.value}, not Ready")

    async def _render_on(
        self,
        client: InfrahubClient,
        service: InfrahubServices,
        prefect_client: PrefectClient,
        webhook_id: str,
        artifact_id: str,
        branch: str,
        previous_requests: int,
    ) -> CoreArtifact:
        """Deliver the one new render request of the artifact on the branch and return the artifact once Ready."""
        events = await self._render_requests(
            prefect_client=prefect_client, artifact_id=artifact_id, branch=branch, count=previous_requests + 1
        )
        assert len(events) == previous_requests + 1
        await self._deliver(service=service, webhook_id=webhook_id, event=events[-1])
        return await self._wait_until_ready(client=client, artifact_id=artifact_id, branch=branch)

    async def test_branch_change_renders_through_the_engine_and_again_on_merge(
        self,
        client: InfrahubClient,
        service: InfrahubServices,
        prefect_client: PrefectClient,
        engine: ReferenceEngine,
        webhook_id: str,
        edge_routers: dict[str, str],
        definition_id: str,
        run_logs: RunLogRecorder,
    ) -> None:
        """A data change on a branch renders once through the engine, passes the check, and renders again on merge.

        `run_logs` records the delivery logs of every render in this class, which the next test reads.
        """
        main = "main"
        for name, device_id in edge_routers.items():
            artifact = await self._artifact(client=client, device_id=device_id, branch=main)
            assert artifact.status.value == ArtifactStatus.PENDING.value
            ready = await self._render_on(
                client=client,
                service=service,
                prefect_client=prefect_client,
                webhook_id=webhook_id,
                artifact_id=artifact.id,
                branch=main,
                previous_requests=0,
            )
            assert await client.object_store.get(identifier=ready.storage_id.value) == _expected_config(
                name=name, descriptions={"ge-0/0/0": "uplink"}
            )
        main_requests = len(engine.received)

        await client.branch.create(branch_name=BRANCH_NAME, sync_with_git=False)
        interfaces = await client.filters(
            kind=TestKind.VIRTUAL_INTERFACE, device__ids=[edge_routers["edge-01"]], branch=BRANCH_NAME
        )
        interfaces[0].description.value = "uplink to core-01"
        await interfaces[0].save()

        proposed_change = await client.create(
            kind=CoreProposedChange,
            source_branch=BRANCH_NAME,
            destination_branch=main,
            name="describe the uplink",
        )
        await proposed_change.save()

        edge_01 = await self._artifact(client=client, device_id=edge_routers["edge-01"], branch=BRANCH_NAME)
        edge_02 = await self._artifact(client=client, device_id=edge_routers["edge-02"], branch=BRANCH_NAME)
        branch_requests = await self._render_requests(
            prefect_client=prefect_client, artifact_id=edge_01.id, branch=BRANCH_NAME, count=1
        )
        assert [event.payload["data"]["target_name"] for event in branch_requests] == ["edge-01"]
        assert not await self._render_requests(
            prefect_client=prefect_client, artifact_id=edge_02.id, branch=BRANCH_NAME, count=0
        )
        assert edge_01.status.value == ArtifactStatus.PENDING.value
        validator = await client.get(
            kind=CoreArtifactValidator, proposed_change__ids=[proposed_change.id], definition__ids=[definition_id]
        )
        assert validator.state.value == ValidatorState.IN_PROGRESS.value
        checks = await client.filters(kind=CoreArtifactCheck, validator__ids=[validator.id])
        assert [check.conclusion.value for check in checks] == [ValidatorConclusion.UNKNOWN.value]

        await self._deliver(service=service, webhook_id=webhook_id, event=branch_requests[0])
        edge_01 = await self._wait_until_ready(client=client, artifact_id=edge_01.id, branch=BRANCH_NAME)
        assert await client.object_store.get(identifier=edge_01.storage_id.value) == _expected_config(
            name="edge-01", descriptions={"ge-0/0/0": "uplink to core-01"}
        )
        check = await client.get(kind=CoreArtifactCheck, id=checks[0].id)
        assert check.conclusion.value == ValidatorConclusion.SUCCESS.value
        validator = await client.get(kind=CoreArtifactValidator, id=validator.id)
        assert validator.state.value == ValidatorState.COMPLETED.value
        assert validator.conclusion.value == ValidatorConclusion.SUCCESS.value
        assert len(engine.received) == main_requests + 1

        proposed_change.state.value = ProposedChangeState.MERGED.value
        await proposed_change.save()

        edge_01_main = await self._render_on(
            client=client,
            service=service,
            prefect_client=prefect_client,
            webhook_id=webhook_id,
            artifact_id=edge_01.id,
            branch=main,
            previous_requests=1,
        )
        assert engine.received[-1].data["branch"] == main
        assert engine.received[-1].data["target_name"] == "edge-01"
        assert await client.object_store.get(identifier=edge_01_main.storage_id.value) == _expected_config(
            name="edge-01", descriptions={"ge-0/0/0": "uplink to core-01"}
        )
        assert {request.callback_status for request in engine.received} == {204}

    async def test_render_token_is_not_stored(
        self, client: InfrahubClient, engine: ReferenceEngine, webhook_id: str, run_logs: RunLogRecorder
    ) -> None:
        """No token the engine received can be read back from events, task parameters, captures or run logs."""
        tokens = {request.token for request in engine.received}
        assert len(tokens) == len(engine.received) == 5

        artifact_ids = sorted({request.data["artifact_id"] for request in engine.received})
        events = json.dumps(
            await client.execute_graphql(query=QUERY_RENDER_REQUESTED_EVENTS, variables={"artifact_ids": artifact_ids})
        )
        tasks = await client.execute_graphql(query=QUERY_WEBHOOK_TASKS, variables={"webhook_id": webhook_id})
        deliveries = tasks["InfrahubTask"]["edges"]
        assert [delivery["node"]["workflow"] for delivery in deliveries] == ["webhook-send"] * 5
        assert all(delivery["node"]["parameters"]["render_request"] for delivery in deliveries)
        assert [delivery["node"]["http_request"]["headers"][RENDER_TOKEN_HEADER] for delivery in deliveries] == [
            "***"
        ] * 5
        outgoing = [message for message in run_logs.messages if message.startswith("Webhook 'reference-engine'")]
        assert len(outgoing) == 5

        stored = "\n".join([events, json.dumps(tasks), *run_logs.messages])
        for request in engine.received:
            assert request.data["render_id"] in events
            assert request.token not in stored

    async def _render_request_ids(
        self, client: InfrahubClient, edge_routers: dict[str, str], branch: str
    ) -> dict[str, str | None]:
        """Return the render request each target's artifact on the branch waits for, by target name."""
        return {
            name: (await self._artifact(client=client, device_id=device_id, branch=branch)).render_request_id.value
            for name, device_id in edge_routers.items()
        }

    async def _render_request_counts(
        self,
        client: InfrahubClient,
        prefect_client: PrefectClient,
        edge_routers: dict[str, str],
        branch: str,
        count: int,
    ) -> dict[str, int]:
        """Wait for `count` render requests of each target's artifact on the branch and return how many arrived."""
        counts = {}
        for name, device_id in edge_routers.items():
            artifact = await self._artifact(client=client, device_id=device_id, branch=branch)
            events = await self._render_requests(
                prefect_client=prefect_client, artifact_id=artifact.id, branch=branch, count=count
            )
            assert events[-1].payload["data"]["render_id"] == artifact.render_request_id.value
            counts[name] = len(events)
        return counts

    async def _import_git_branch(
        self, client: InfrahubClient, file_repo: FileRepo, branch: str, files: dict[str, str]
    ) -> None:
        """Commit the files on a new Git branch and have the Infrahub branch of the same name track it."""
        file_repo.repo.git.checkout("-b", branch, "main")
        for path, content in files.items():
            (Path(file_repo.path) / path).write_text(content, encoding="utf-8")
        file_repo.repo.git.add(".")
        commit = file_repo.repo.index.commit(f"commit on {branch}").hexsha
        file_repo.repo.git.checkout("main")

        await client.branch.create(branch_name=branch, sync_with_git=False)
        repository = await client.get(kind=CoreReadOnlyRepository, name__value=REPOSITORY_NAME, branch=branch)
        repository.ref.value = branch
        await repository.save()
        repository = await client.get(kind=CoreReadOnlyRepository, name__value=REPOSITORY_NAME, branch=branch)
        assert repository.commit.value == commit

    async def test_version_change_on_a_branch_renders_every_target(
        self,
        client: InfrahubClient,
        prefect_client: PrefectClient,
        file_repo: FileRepo,
        edge_routers: dict[str, str],
        definition_id: str,
    ) -> None:
        """A new version imported on a branch, then its proposed change, each request one render of every target."""
        branch = "template-1-1"
        main_request_ids = await self._render_request_ids(client=client, edge_routers=edge_routers, branch="main")

        await self._import_git_branch(
            client=client,
            file_repo=file_repo,
            branch=branch,
            files={".infrahub.yml": yaml.safe_dump(_repository_config(version="1.6.0"))},
        )

        branch_request_ids = await self._render_request_ids(client=client, edge_routers=edge_routers, branch=branch)
        assert all(branch_request_ids[name] not in {None, main_request_ids[name]} for name in edge_routers), (
            branch_request_ids
        )
        assert await self._render_request_counts(
            client=client, prefect_client=prefect_client, edge_routers=edge_routers, branch=branch, count=1
        ) == {"edge-01": 1, "edge-02": 1, "edge-03": 1}

        proposed_change = await client.create(
            kind=CoreProposedChange, source_branch=branch, destination_branch="main", name="release template 1.6.0"
        )
        await proposed_change.save()

        assert await self._render_request_counts(
            client=client, prefect_client=prefect_client, edge_routers=edge_routers, branch=branch, count=2
        ) == {"edge-01": 2, "edge-02": 2, "edge-03": 2}
        validator = await client.get(
            kind=CoreArtifactValidator, proposed_change__ids=[proposed_change.id], definition__ids=[definition_id]
        )
        checks = await client.filters(kind=CoreArtifactCheck, validator__ids=[validator.id])
        assert len(checks) == 3

    async def test_unrelated_commit_on_a_branch_renders_nothing(
        self,
        client: InfrahubClient,
        prefect_client: PrefectClient,
        file_repo: FileRepo,
        edge_routers: dict[str, str],
        definition_id: str,
    ) -> None:
        branch = "docs-update"
        main_request_ids = await self._render_request_ids(client=client, edge_routers=edge_routers, branch="main")

        await self._import_git_branch(
            client=client, file_repo=file_repo, branch=branch, files={"README.md": "Startup configurations\n"}
        )

        assert await self._render_request_ids(client=client, edge_routers=edge_routers, branch=branch) == (
            main_request_ids
        )
        for device_id in edge_routers.values():
            artifact = await self._artifact(client=client, device_id=device_id, branch=branch)
            assert not await self._render_requests(
                prefect_client=prefect_client, artifact_id=artifact.id, branch=branch, count=0
            )

    async def test_manual_generation_renders_every_target(
        self,
        client: InfrahubClient,
        prefect_client: PrefectClient,
        edge_routers: dict[str, str],
        definition_id: str,
    ) -> None:
        branch = "regenerate"
        await client.branch.create(branch_name=branch, sync_with_git=False)

        await client._post(
            url=f"{client.address}/api/artifact/generate/{definition_id}?branch={branch}", payload={"nodes": []}
        )

        assert await self._render_request_counts(
            client=client, prefect_client=prefect_client, edge_routers=edge_routers, branch=branch, count=1
        ) == {"edge-01": 1, "edge-02": 1, "edge-03": 1}
