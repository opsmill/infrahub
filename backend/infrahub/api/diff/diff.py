from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, Request
from infrahub_sdk.utils import compare_lists

from infrahub import config
from infrahub.api.dependencies import get_branch_dep, get_current_user, get_db
from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.constants import BranchSupportType, DiffAction, InfrahubKind
from infrahub.core.diff.branch_differ import BranchDiffer
from infrahub.core.diff.payload import (
    ArtifactTarget,
    BranchDiff,
    BranchDiffArtifact,
    BranchDiffArtifactStorage,
    BranchDiffFile,
    BranchDiffNode,
    BranchDiffRepository,
    DiffPayload,
    generate_diff_payload,
    get_display_labels_per_kind,
)
from infrahub.core.schema_manager import INTERNAL_SCHEMA_NODE_KINDS
from infrahub.database import InfrahubDatabase  # noqa: TCH001

from .validation_models import DiffQueryValidated

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices

# pylint: disable=too-many-branches,too-many-lines

router = APIRouter(prefix="/diff")


@router.get("/data")
async def get_diff_data(
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = True,
    _: str = Depends(get_current_user),
) -> BranchDiff:
    query = DiffQueryValidated(branch=branch, time_from=time_from, time_to=time_to, branch_only=branch_only)

    diff = await BranchDiffer.init(
        db=db,
        branch=branch,
        diff_from=query.time_from,
        diff_to=query.time_to,
        branch_only=query.branch_only,
        namespaces_exclude=["Schema"],
    )
    schema = registry.schema.get_full(branch=branch)
    diff_payload = DiffPayload(db=db, diff=diff, kinds_to_include=list(schema.keys()))
    return await diff_payload.generate_diff_payload()


@router.get("/schema")
async def get_diff_schema(
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = True,
    _: str = Depends(get_current_user),
) -> BranchDiff:
    query = DiffQueryValidated(branch=branch, time_from=time_from, time_to=time_to, branch_only=branch_only)
    diff = await BranchDiffer.init(
        db=db,
        branch=branch,
        diff_from=query.time_from,
        diff_to=query.time_to,
        branch_only=query.branch_only,
        kinds_include=INTERNAL_SCHEMA_NODE_KINDS,
    )
    diff_payload = DiffPayload(db=db, diff=diff)
    return await diff_payload.generate_diff_payload()


@router.get("/files")
async def get_diff_files(
    request: Request,
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = True,
    _: str = Depends(get_current_user),
) -> Dict[str, Dict[str, BranchDiffRepository]]:
    response: Dict[str, Dict[str, BranchDiffRepository]] = defaultdict(dict)
    service: InfrahubServices = request.app.state.service

    # Query the Diff for all files and repository from the database
    diff = await BranchDiffer.init(
        db=db, branch=branch, diff_from=time_from, diff_to=time_to, branch_only=branch_only, service=service
    )
    diff_files = await diff.get_files()

    for branch_name, items in diff_files.items():
        for item in items:
            if item.repository not in response[branch_name]:
                response[branch_name][item.repository] = BranchDiffRepository(
                    id=item.repository,
                    display_name=f"Repository ({item.repository})",
                    commit_from=item.commit_from,
                    commit_to=item.commit_to,
                    branch=branch_name,
                )

            response[branch_name][item.repository].files.append(BranchDiffFile(**item.to_graphql()))

    return response


@router.get("/artifacts")
async def get_diff_artifacts(
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    branch_only: bool = False,
    _: str = Depends(get_current_user),
) -> Dict[str, BranchDiffArtifact]:
    response = {}

    default_branch_name = config.SETTINGS.main.default_branch
    # Query the Diff for all artifacts
    diff = await BranchDiffer.init(
        db=db,
        branch=branch,
        diff_from=time_from,
        diff_to=time_to,
        branch_only=branch_only,
        kinds_include=[InfrahubKind.ARTIFACT],
        branch_support=[BranchSupportType.AWARE, BranchSupportType.LOCAL],
    )
    payload = await generate_diff_payload(diff=diff, db=db, kinds_to_include=[InfrahubKind.ARTIFACT])

    # Extract the ids of all the targets associated with these artifacts and query the display label for all of them
    artifact_ids_branch = [node.id for node in payload[branch.name]]
    artifact_ids_main = [node.id for node in payload[default_branch_name]]
    _, _, only_in_main = compare_lists(list1=artifact_ids_branch, list2=artifact_ids_main)

    targets = await registry.manager.query(
        db=db,
        schema="CoreArtifactTarget",
        filters={"artifacts__ids": artifact_ids_branch},
        prefetch_relationships=True,
        branch=branch,
    )

    if only_in_main:
        targets_in_main = await registry.manager.query(
            db=db,
            schema="CoreArtifactTarget",
            filters={"artifacts__ids": only_in_main},
            prefetch_relationships=True,
            branch=default_branch_name,
        )
        targets += targets_in_main

    target_per_kinds = defaultdict(list)
    target_per_artifact: Dict[str, ArtifactTarget] = {}
    for target in targets:
        for artifact_id in await target.artifacts.get_peers(db=db):
            target_per_artifact[artifact_id] = ArtifactTarget(id=target.id, kind=target.get_kind())
            target_per_kinds[target.get_kind()].append(target.id)

    display_labels = {}
    for kind, ids in target_per_kinds.items():
        display_labels.update(await get_display_labels_per_kind(kind=kind, ids=ids, branch_name=branch.name, db=db))

    # If an artifact has been already created in main, it will appear as CREATED insted of UPDATED
    # To fix that situation, we extract all unique identifier for an artifact (target_id, definition_id) in order to make it easier to search later
    artifacts_in_main: Dict[Tuple[str, str], BranchDiffNode] = {}
    for node in payload[default_branch_name]:
        if (
            node.action != DiffAction.ADDED
            or "storage_id" not in node.elements
            or "checksum" not in node.elements
            or "definition" not in node.elements
        ):
            continue

        target = target_per_artifact.get(node.id, None)
        if not target:
            continue
        definition_id = node.elements["definition"].peer.new.id
        artifacts_in_main[(target.id, definition_id)] = node

    for node in payload[branch.name]:
        if "storage_id" not in node.elements or "checksum" not in node.elements:
            continue

        display_label = node.display_label
        target = target_per_artifact.get(node.id, None)
        if target:
            target.display_label = display_labels.get(target.id, None)
            if target.display_label:
                display_label = f"{target.display_label} - {node.display_label}"

        diff_artifact = BranchDiffArtifact(
            id=node.id, action=node.action, branch=branch.name, display_label=display_label, target=target
        )

        if node.action in [DiffAction.UPDATED, DiffAction.ADDED]:
            diff_artifact.item_new = BranchDiffArtifactStorage(
                storage_id=node.elements["storage_id"].value.value.new,
                checksum=node.elements["checksum"].value.value.new,
            )

        if node.action in [DiffAction.UPDATED, DiffAction.REMOVED]:
            diff_artifact.item_previous = BranchDiffArtifactStorage(
                storage_id=node.elements["storage_id"].value.value.previous,
                checksum=node.elements["checksum"].value.value.previous,
            )

        # if there is an artifact in main with the same target.id / definition.id, we merge them
        if (
            node.action == DiffAction.ADDED
            and "definition" in node.elements
            and (target.id, node.elements["definition"].peer.new.id) in artifacts_in_main
        ):
            diff_artifact.action = DiffAction.UPDATED
            node_in_main = artifacts_in_main[(target.id, node.elements["definition"].peer.new.id)]
            diff_artifact.item_previous = BranchDiffArtifactStorage(
                storage_id=node_in_main.elements["storage_id"].value.value.new,
                checksum=node_in_main.elements["checksum"].value.value.new,
            )

        response[node.id] = diff_artifact

    return response
