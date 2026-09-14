import logging
from dataclasses import dataclass
from types import TracebackType
from typing import Any, override

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.exceptions import ServerNotResponsiveError, TrackingGroupCleanupError
from typing_extensions import Self

from infrahub.core.constants import ContentType, RepositoryObjects
from infrahub.exceptions import TransformError
from infrahub.git import InfrahubRepository
from infrahub.git.integrator import serialize_artifact_content


@dataclass
class SerializationCase:
    name: str
    content: Any
    content_type: str
    expected: str


SERIALIZATION_CASES = [
    SerializationCase(
        name="dict_as_json",
        content={"key1": "value1"},
        content_type=ContentType.APPLICATION_JSON.value,
        expected='{\n  "key1": "value1"\n}',
    ),
    SerializationCase(
        name="dict_as_yaml",
        content={"key1": "value1"},
        content_type=ContentType.APPLICATION_YAML.value,
        expected="key1: value1\n",
    ),
    SerializationCase(
        name="string_as_text",
        content="Lorem ipsum",
        content_type=ContentType.TEXT_PLAIN.value,
        expected="Lorem ipsum",
    ),
    SerializationCase(
        name="empty_string_is_a_valid_payload",
        content="",
        content_type=ContentType.TEXT_PLAIN.value,
        expected="",
    ),
]


@pytest.mark.parametrize("case", SERIALIZATION_CASES, ids=lambda c: c.name)
def test_serialize_artifact_content(case: SerializationCase) -> None:
    assert (
        serialize_artifact_content(
            content=case.content,
            content_type=case.content_type,
            repository_name="my-repository",
            commit="d9b3b6f9e2c0a1d4e5f60718293a4b5c6d7e8f90",
            location="transform01.py::Transform01",
        )
        == case.expected
    )


def test_serialize_artifact_content_without_payload() -> None:
    with pytest.raises(
        TransformError, match=r"^The transform at transform01\.py::Transform01 did not return a payload$"
    ):
        serialize_artifact_content(
            content=None,
            content_type=ContentType.TEXT_PLAIN.value,
            repository_name="my-repository",
            commit="d9b3b6f9e2c0a1d4e5f60718293a4b5c6d7e8f90",
            location="transform01.py::Transform01",
        )


REFUSED_OBJECT_ID = "17d5e3f4-1a2b-4c6d-8e9f-0a1b2c3d4e5f"
REFUSAL_REASON = "Cannot delete BuiltinTag. It is linked to mandatory relationship tags on node TestingPerson"


@dataclass
class TrackingCall:
    identifier: str | None
    branch: str | None
    delete_unused_nodes: bool
    group_type: str | None
    group_params: dict[str, Any] | None


class RecordingTrackingClient(InfrahubClient):
    """Records the tracking context each import phase opens, and closes it cleanly."""

    def __init__(self) -> None:
        super().__init__(config=Config(address="http://mock"))
        self.tracking_calls: list[TrackingCall] = []

    @override
    def start_tracking(
        self,
        identifier: str | None = None,
        params: dict[str, Any] | None = None,
        delete_unused_nodes: bool = False,
        group_type: str | None = None,
        group_params: dict[str, Any] | None = None,
        branch: str | None = None,
    ) -> Self:
        self.tracking_calls.append(
            TrackingCall(
                identifier=identifier,
                branch=branch,
                delete_unused_nodes=delete_unused_nodes,
                group_type=group_type,
                group_params=group_params,
            )
        )
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class RefusingTrackingClient(RecordingTrackingClient):
    """A client whose server refuses to delete the objects the phase no longer tracks."""

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        raise TrackingGroupCleanupError(failures={REFUSED_OBJECT_ID: REFUSAL_REASON})


class UnreachableTrackingClient(RecordingTrackingClient):
    """A client whose cleanup is interrupted by something that is not about any object."""

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        raise ServerNotResponsiveError(url="http://mock/graphql/main")


class TestImportFilePaths:
    @pytest.fixture(autouse=True)
    def run_logger(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("infrahub.git.integrator.get_run_logger", lambda: logging.getLogger("test"))

    async def test_refused_cleanup_does_not_abort_the_phase(
        self, git_repo_01: InfrahubRepository, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Importing objects is one phase of several, so a refused deletion must not end the import.

        The refused objects stay in the tracking group and the next import retries them.
        """
        client = RefusingTrackingClient()
        git_repo_01.client = client

        with caplog.at_level(logging.WARNING, logger="test"):
            await git_repo_01._import_file_paths(
                branch_name="main", commit="", files_pathes=[], object_type=RepositoryObjects.OBJECT
            )

        assert client.tracking_calls == [
            TrackingCall(
                identifier=f"group-repo-object-{git_repo_01.id}",
                branch="main",
                delete_unused_nodes=True,
                group_type="CoreRepositoryGroup",
                group_params={"content": "object", "repository": str(git_repo_01.id)},
            )
        ]
        assert caplog.messages == [
            f"Unable to delete 1 object(s) no longer defined in the repository: "
            f"Unable to delete 1 unused member(s) of the tracking group: {REFUSED_OBJECT_ID} ({REFUSAL_REASON})"
        ]

    async def test_interrupted_cleanup_fails_the_phase(self, git_repo_01: InfrahubRepository) -> None:
        """Only a refusal is recoverable; an unreachable server must still fail the import."""
        git_repo_01.client = UnreachableTrackingClient()

        with pytest.raises(ServerNotResponsiveError, match=r"^Unable to read from 'http://mock/graphql/main'\.$"):
            await git_repo_01._import_file_paths(
                branch_name="main", commit="", files_pathes=[], object_type=RepositoryObjects.OBJECT
            )
