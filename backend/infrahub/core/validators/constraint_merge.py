from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.validators.uniqueness.deduplicator import UniquenessConstraintDeduplicator

if TYPE_CHECKING:
    from infrahub.core.models import SchemaUpdateConstraintInfo
    from infrahub.core.schema.schema_branch import SchemaBranch


class ConstraintInfoMerger:
    """Combine constraint infos from several producers into the set of checks to run.

    First the same constraint produced by more than one producer is collapsed onto a single entry;
    then node-level uniqueness checks already covered by an implicated generic are dropped.
    """

    def __init__(self, deduplicator: UniquenessConstraintDeduplicator) -> None:
        self.deduplicator = deduplicator

    def merge(self, *constraint_lists: list[SchemaUpdateConstraintInfo]) -> list[SchemaUpdateConstraintInfo]:
        """Collapse the same constraint from multiple producers onto one entry.

        A constraint both broadened by a schema change (full population) and hit by a data change
        (node-scoped) must re-check every node, so a ``None`` node_uuids always wins and two
        node-scoped entries union.
        """
        merged: dict[tuple[str, str], SchemaUpdateConstraintInfo] = {}
        for constraint_list in constraint_lists:
            for constraint in constraint_list:
                key = (constraint.constraint_name, constraint.path.get_path())
                existing = merged.get(key)
                if existing is None:
                    merged[key] = constraint
                elif existing.node_uuids is None:
                    continue
                elif constraint.node_uuids is None:
                    merged[key] = constraint
                else:
                    merged[key] = existing.model_copy(
                        update={"node_uuids": sorted(set(existing.node_uuids) | set(constraint.node_uuids))}
                    )

        return self.deduplicator.deduplicate(list(merged.values()))


def build_constraint_info_merger(schema_branch: SchemaBranch) -> ConstraintInfoMerger:
    return ConstraintInfoMerger(deduplicator=UniquenessConstraintDeduplicator(schema_branch=schema_branch))
