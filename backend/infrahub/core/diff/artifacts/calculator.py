from collections import defaultdict

from infrahub.core.branch.models import Branch
from infrahub.core.constants import DiffAction, InfrahubKind
from infrahub.database import InfrahubDatabase

from ..model.diff import ArtifactTarget, BranchDiffArtifact, BranchDiffArtifactStorage
from ..payload_builder import get_display_labels_per_kind
from ..query.artifact import ArtifactDiffQuery


class ArtifactDiffCalculator:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def calculate(self, source_branch: Branch, target_branch: Branch) -> list[BranchDiffArtifact]:
        artifact_schema = self.db.schema.get(name=InfrahubKind.ARTIFACT, branch=source_branch, duplicate=False)
        target_rel = artifact_schema.get_relationship(name="object")
        definition_rel = artifact_schema.get_relationship(name="definition")
        query = await ArtifactDiffQuery.init(
            db=self.db,
            branch=source_branch,
            target_branch=target_branch,
            target_rel_identifier=target_rel.get_identifier(),
            definition_rel_identifier=definition_rel.get_identifier(),
        )
        await query.execute(db=self.db)

        artifact_diffs = []
        for result in query.get_results():
            source_artifact_node = result.get_node(label="source_artifact")
            artifact_id = str(source_artifact_node.get("uuid"))
            try:
                target_node = result.get_node(label="target_node")
                artifact_target = ArtifactTarget(
                    id=str(target_node.get("uuid")),
                    kind=str(target_node.get("kind")),
                    display_label=None,
                )
            except ValueError:
                artifact_target = None
            source_storage_id = result.get_as_str("source_storage_id")
            source_checksum = result.get_as_str("source_checksum")
            new_storage: BranchDiffArtifactStorage | None = None
            if source_storage_id and source_checksum:
                new_storage = BranchDiffArtifactStorage(
                    storage_id=source_storage_id,
                    checksum=source_checksum,
                )
            target_storage_id = result.get_as_str("target_storage_id")
            target_checksum = result.get_as_str("target_checksum")
            old_storage: BranchDiffArtifactStorage | None = None
            if target_storage_id and target_checksum:
                old_storage = BranchDiffArtifactStorage(
                    storage_id=target_storage_id,
                    checksum=target_checksum,
                )
            artifact_diffs.append(
                BranchDiffArtifact(
                    branch=source_branch.name,
                    id=artifact_id,
                    display_label=None,
                    action=DiffAction.UPDATED if old_storage else DiffAction.ADDED,
                    target=artifact_target,
                    item_new=new_storage,
                    item_previous=old_storage,
                )
            )
        await self._add_display_labels(source_branch=source_branch, artifact_diffs=artifact_diffs)

        return artifact_diffs

    async def _add_display_labels(self, source_branch: Branch, artifact_diffs: list[BranchDiffArtifact]) -> None:
        ids_by_kind: dict[str, set[str]] = defaultdict(set)
        for artifact_diff in artifact_diffs:
            ids_by_kind[InfrahubKind.ARTIFACT].add(artifact_diff.id)
            if artifact_diff.target:
                ids_by_kind[artifact_diff.target.kind].add(artifact_diff.target.id)

        display_labels_by_id: dict[str, str] = {}
        for kind, node_ids in ids_by_kind.items():
            display_label_map = await get_display_labels_per_kind(
                db=self.db, branch_name=source_branch.name, kind=kind, ids=list(node_ids)
            )
            display_labels_by_id.update(display_label_map)

        for artifact_diff in artifact_diffs:
            artifact_diff.display_label = display_labels_by_id.get(artifact_diff.id)
            if not artifact_diff.target:
                continue
            artifact_diff.target.display_label = display_labels_by_id.get(artifact_diff.target.id)
            if artifact_diff.target.display_label and artifact_diff.display_label:
                artifact_diff.display_label = f"{artifact_diff.target.display_label} - {artifact_diff.display_label}"
