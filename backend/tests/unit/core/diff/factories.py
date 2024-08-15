from polyfactory.factories import DataclassFactory

from infrahub.core.diff.model.path import (
    CalculatedDiffs,
    DiffAttribute,
    DiffNode,
    DiffProperty,
    DiffRelationship,
    DiffRoot,
    DiffSingleRelationship,
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)


class EnrichedPropertyFactory(DataclassFactory[EnrichedDiffProperty]): ...


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
    contains_conflict = False


class EnrichedRelationshipElementFactory(DataclassFactory[EnrichedDiffSingleRelationship]):
    __set_as_default_factory_for_type__ = True
    num_added = 0
    num_updated = 0
    num_removed = 0
    num_conflicts = 0
    contains_conflict = False


class EnrichedNodeFactory(DataclassFactory[EnrichedDiffNode]):
    __set_as_default_factory_for_type__ = True
    num_added = 0
    num_updated = 0
    num_removed = 0
    num_conflicts = 0
    contains_conflict = False


class EnrichedRootFactory(DataclassFactory[EnrichedDiffRoot]):
    num_added = 0
    num_updated = 0
    num_removed = 0
    num_conflicts = 0
    contains_conflict = False


class CalculatedDiffsFactory(DataclassFactory[CalculatedDiffs]): ...


class DiffPropertyFactory(DataclassFactory[DiffProperty]): ...


class DiffAttributeFactory(DataclassFactory[DiffAttribute]): ...


class DiffSingleRelationshipFactory(DataclassFactory[DiffSingleRelationship]): ...


class DiffRelationshipFactory(DataclassFactory[DiffRelationship]): ...


class DiffNodeFactory(DataclassFactory[DiffNode]): ...


class DiffRootFactory(DataclassFactory[DiffRoot]): ...
