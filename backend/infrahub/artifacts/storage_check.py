from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.constants import ArtifactStatus
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreArtifact, CoreArtifactDefinition
from infrahub.exceptions import NodeNotFoundError
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.log import get_run_logger
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.workflow import InfrahubWorkflow
    from infrahub.storage import InfrahubObjectStorage


class ArtifactStorageChecker:
    """Regenerate the artifacts whose stored file is missing or no longer matches their checksum."""

    def __init__(self, db: InfrahubDatabase, storage: InfrahubObjectStorage, workflow: InfrahubWorkflow) -> None:
        self.db = db
        self.storage = storage
        self.workflow = workflow

    async def check(self, branch: Branch) -> None:
        """Queue one regeneration per artifact definition that has ready artifacts with a broken stored file."""
        context = InfrahubContext.init(
            branch=branch, account=AccountSession(auth_type=AuthType.NONE, authenticated=False, account_id="")
        )
        for definition in await NodeManager.query(db=self.db, schema=CoreArtifactDefinition, branch=branch):
            artifacts = await NodeManager.query(
                db=self.db,
                schema=CoreArtifact,
                branch=branch,
                filters={"definition__ids": [definition.id], "status__value": ArtifactStatus.READY.value},
            )
            broken = sorted([artifact.id for artifact in artifacts if not await self._stored_file_matches(artifact)])
            if not broken:
                continue

            get_run_logger().warning(
                f"Regenerating {len(broken)} artifacts of {definition.name.value!r} whose stored file is missing"
                " or does not match their checksum"
            )
            await self.workflow.submit_workflow(
                workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
                context=context,
                parameters={
                    "model": RequestArtifactDefinitionGenerate(
                        artifact_definition_id=definition.id,
                        artifact_definition_name=definition.name.value,
                        branch=branch.name,
                        limit=broken,
                    )
                },
            )

    async def _stored_file_matches(self, artifact: CoreArtifact) -> bool:
        storage_id = artifact.storage_id.value
        if storage_id is None:
            return False
        try:
            content = await asyncio.to_thread(self.storage.retrieve_binary, identifier=storage_id)
        except NodeNotFoundError:
            return False
        return hashlib.md5(content, usedforsecurity=False).hexdigest() == artifact.checksum.value
