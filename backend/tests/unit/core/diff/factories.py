from uuid import uuid4

from polyfactory.factories import DataclassFactory

from infrahub.core.diff.model.path import (
    BranchTrackingId,
    CalculatedDiffs,
    DiffAttribute,
    DiffNode,
    DiffProperty,
    DiffRelationship,
    DiffRoot,
    DiffSingleRelationship,
    EnrichedDiffAttribute,
    EnrichedDiffConflict,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)


class EnrichedConflictFactory(DataclassFactory[EnrichedDiffConflict]):
    __set_as_default_factory_for_type__ = True
    base_branch_label = None
    diff_branch_label = None


class EnrichedPropertyFactory(DataclassFactory[EnrichedDiffProperty]):
    __set_as_default_factory_for_type__ = True
    conflict = None
    previous_label = None
    new_label = None


class EnrichedAttributeFactory(DataclassFactory[EnrichedDiffAttribute]):
    __set_as_default_factory_for_type__ = True
    num_added = 0
    num_updated = 0
    num_removed = 0
    num_conflicts = 0
    contains_conflict = False


class EnrichedRelationshipGroupFactory(DataclassFactory[EnrichedDiffRelationship]):
    __set_as_default_factory_for_type__ = True
    num_added = 0
    num_updated = 0
    num_removed = 0
    num_conflicts = 0
    nodes = set()
    contains_conflict = False


class EnrichedRelationshipElementFactory(DataclassFactory[EnrichedDiffSingleRelationship]):
    __set_as_default_factory_for_type__ = True
    num_added = 0
    num_updated = 0
    num_removed = 0
    num_conflicts = 0
    contains_conflict = False
    conflict = None


class EnrichedNodeFactory(DataclassFactory[EnrichedDiffNode]):
    __set_as_default_factory_for_type__ = True
    num_added = 0
    num_updated = 0
    num_removed = 0
    num_conflicts = 0
    contains_conflict = False
    conflict = None


def get_tracking_id() -> BranchTrackingId:
    return BranchTrackingId(name=str(uuid4()))


class EnrichedRootFactory(DataclassFactory[EnrichedDiffRoot]):
    tracking_id = get_tracking_id
    num_added = 0
    num_updated = 0
    num_removed = 0
    num_conflicts = 0
    contains_conflict = False
    exists_on_database = False


class CalculatedDiffsFactory(DataclassFactory[CalculatedDiffs]): ...


class DiffPropertyFactory(DataclassFactory[DiffProperty]): ...


class DiffAttributeFactory(DataclassFactory[DiffAttribute]): ...


class DiffSingleRelationshipFactory(DataclassFactory[DiffSingleRelationship]): ...


class DiffRelationshipFactory(DataclassFactory[DiffRelationship]): ...


class DiffNodeFactory(DataclassFactory[DiffNode]): ...


class DiffRootFactory(DataclassFactory[DiffRoot]): ...
