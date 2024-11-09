from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, Depends, Request

from infrahub.api.dependencies import get_branch_dep, get_current_user, get_db
from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.constants import DiffAction, InfrahubKind
from infrahub.core.diff.branch_differ import BranchDiffer
from infrahub.core.diff.model.diff import (
    ArtifactTarget,
    BranchDiffArtifact,
    BranchDiffArtifactStorage,
    BranchDiffFile,
    BranchDiffRepository,
)
from infrahub.core.diff.payload_builder import (
    get_display_labels_per_kind,
)
from infrahub.core.protocols import CoreArtifact
from infrahub.database import InfrahubDatabase  # noqa: TCH001

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


router = APIRouter(prefix="/diff")


@router.get("/files")
async def get_diff_files(
    request: Request,
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = True,
    _: str = Depends(get_current_user),
) -> dict[str, dict[str, BranchDiffRepository]]:
    response: dict[str, dict[str, BranchDiffRepository]] = defaultdict(dict)
    service: InfrahubServices = request.app.state.service

    # Query the Diff for all files and repository from the database
    diff = await BranchDiffer.init(
        db=db, branch=branch, diff_from=time_from, diff_to=time_to, branch_only=branch_only, service=service
    )
    diff_files = await diff.get_files()

    for branch_name, items in diff_files.items():
        for item in items:
            repository_id = item.repository.get_id()
            display_label = await item.repository.render_display_label(db=db)
            if repository_id not in response[branch_name]:
                response[branch_name][repository_id] = BranchDiffRepository(
                    id=repository_id,
                    display_name=display_label or f"Repository ({repository_id})",
                    commit_from=item.commit_from,
                    commit_to=item.commit_to,
                    branch=branch_name,
                )

            response[branch_name][repository_id].files.append(BranchDiffFile(**item.to_graphql()))

    return response


@router.get("/artifacts")
async def get_diff_artifacts(
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    _: str = Depends(get_current_user),
) -> dict[str, BranchDiffArtifact]:
    branch_artifacts = await registry.manager.query(
        db=db,
        branch=branch,
        schema=CoreArtifact,
        prefetch_relationships=True,
    )
    branch_artifacts_map: dict[tuple[str, str], CoreArtifact] = {}
    branch_target_ids: set[str] = set()
    target_ids_by_definition_id_map: dict[str, set[str]] = defaultdict(set)
    for bart in branch_artifacts:
        target_rels = await bart.object.get_relationships(db=db)
        definition_rels = await bart.definition.get_relationships(db=db)
        target_peer_id = target_rels[0].get_peer_id()
        definition_peer_id = definition_rels[0].get_peer_id()
        branch_target_ids.add(target_peer_id)
        target_ids_by_definition_id_map[definition_peer_id].add(target_peer_id)
        branch_artifacts_map[definition_peer_id, target_peer_id] = bart
    main_artifacts_map: dict[tuple[str, str], CoreArtifact] = {}
    possible_main_artifacts = await registry.manager.query(
        db=db,
        branch=registry.default_branch,
        schema=CoreArtifact,
        filters={"definition__ids": list(target_ids_by_definition_id_map.keys())},
        prefetch_relationships=True,
    )
    for pmart in possible_main_artifacts:
        target_rels = await pmart.object.get_relationships(db=db)
        definition_rels = await pmart.definition.get_relationships(db=db)
        target_peer_id = target_rels[0].get_peer_id()
        definition_peer_id = definition_rels[0].get_peer_id()
        if target_peer_id in target_ids_by_definition_id_map[definition_peer_id]:
            main_artifacts_map[definition_peer_id, target_peer_id] = pmart

    # target display labels
    target_map = await registry.manager.get_many(db=db, branch=branch, ids=list(branch_target_ids))
    target_per_kinds: dict[str, set[str]] = defaultdict(set)
    target_per_kinds[InfrahubKind.ARTIFACT] = {bart.get_id() for bart in branch_artifacts}
    serialized_target_map: dict[str, ArtifactTarget] = {}
    for target in target_map.values():
        serialized_target_map[target.get_id()] = ArtifactTarget(id=target.get_id(), kind=target.get_kind())
        target_per_kinds[target.get_kind()].add(target.get_id())

    display_labels_map: dict[str, str] = {}
    for kind, ids in target_per_kinds.items():
        display_labels_map.update(
            await get_display_labels_per_kind(kind=kind, ids=list(ids), branch_name=branch.name, db=db)
        )

    response: dict[str, BranchDiffArtifact] = {}

    for artifact_identifier, artifact in branch_artifacts_map.items():
        action = DiffAction.ADDED
        if artifact_identifier in main_artifacts_map:
            action = DiffAction.UPDATED
        artifact_display_label = display_labels_map.get(artifact.get_id())
        target_rels = await artifact.object.get_relationships(db=db)
        target_peer_id = target_rels[0].get_peer_id()
        serialized_target = serialized_target_map[target_peer_id]
        if not serialized_target.display_label:
            serialized_target.display_label = display_labels_map.get(target_peer_id)
        if serialized_target.display_label:
            artifact_display_label = f"{serialized_target.display_label} - {artifact_display_label}"
        serialized_artifact = BranchDiffArtifact(
            id=artifact.get_id(),
            action=action,
            branch=branch.name,
            display_label=artifact_display_label,
            target=serialized_target,
        )
        if artifact.storage_id.value and artifact.checksum.value:
            serialized_artifact.item_new = BranchDiffArtifactStorage(
                storage_id=artifact.storage_id.value, checksum=artifact.checksum.value
            )
        if artifact_identifier in main_artifacts_map:
            main_artifact = main_artifacts_map[artifact_identifier]
            if main_artifact.storage_id.value and main_artifact.checksum.value:
                serialized_artifact.item_previous = BranchDiffArtifactStorage(
                    storage_id=main_artifact.storage_id.value, checksum=main_artifact.checksum.value
                )
        response[artifact.get_id()] = serialized_artifact
    return response
