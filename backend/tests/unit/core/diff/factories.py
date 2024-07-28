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


class EnrichedAttributeFactory(DataclassFactory[EnrichedDiffAttribute]): ...


class EnrichedRelationshipGroupFactory(DataclassFactory[EnrichedDiffRelationship]): ...


class EnrichedRelationshipElementFactory(DataclassFactory[EnrichedDiffSingleRelationship]): ...


class EnrichedNodeFactory(DataclassFactory[EnrichedDiffNode]): ...


class EnrichedRootFactory(DataclassFactory[EnrichedDiffRoot]): ...


class CalculatedDiffsFactory(DataclassFactory[CalculatedDiffs]): ...


class DiffPropertyFactory(DataclassFactory[DiffProperty]): ...


class DiffAttributeFactory(DataclassFactory[DiffAttribute]): ...


class DiffSingleRelationshipFactory(DataclassFactory[DiffSingleRelationship]): ...


class DiffRelationshipFactory(DataclassFactory[DiffRelationship]): ...


class DiffNodeFactory(DataclassFactory[DiffNode]): ...


class DiffRootFactory(DataclassFactory[DiffRoot]): ...
