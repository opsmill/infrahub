from .builder.constraint.grouped.node_runner import NodeConstraintRunnerDependency
from .builder.constraint.node.grouped_uniqueness import NodeGroupedUniquenessConstraintDependency
from .builder.constraint.node.uniqueness import NodeAttributeUniquenessConstraintDependency
from .builder.constraint.relationship_manager.count import RelationshipCountConstraintDependency
from .builder.constraint.relationship_manager.peer_kind import RelationshipPeerKindConstraintDependency
from .builder.constraint.relationship_manager.profiles_kind import RelationshipProfilesKindConstraintDependency
from .builder.constraint.schema.aggregated import AggregatedSchemaConstraintsDependency
from .builder.constraint.schema.attribute_regex import SchemaAttributeRegexConstraintDependency
from .builder.constraint.schema.attribute_uniqueness import SchemaAttributeUniqueConstraintDependency
from .builder.constraint.schema.relationship_optional import SchemaRelationshipOptionalConstraintDependency
from .builder.constraint.schema.uniqueness import SchemaUniquenessConstraintDependency
from .builder.diff.calculator import DiffCalculatorDependency
from .builder.diff.combiner import DiffCombinerDependency
from .builder.diff.conflict_transferer import DiffConflictTransfererDependency
from .builder.diff.coordinator import DiffCoordinatorDependency
from .builder.diff.data_check_synchronizer import DiffDataCheckSynchronizerDependency
from .builder.diff.diff_merger import DiffMergerDependency
from .builder.diff.enricher.aggregated import DiffAggregatedEnricherDependency
from .builder.diff.enricher.cardinality_one import DiffCardinalityOneEnricherDependency
from .builder.diff.enricher.hierarchy import DiffHierarchyEnricherDependency
from .builder.diff.ipam_diff_parser import IpamDiffParserDependency
from .builder.diff.repository import DiffRepositoryDependency
from .builder.ip.kinds_getter import IpamKindsGetterDependency
from .builder.node.delete_validator import NodeDeleteValidatorDependency
from .component.registry import ComponentDependencyRegistry


def build_component_registry() -> ComponentDependencyRegistry:
    component_registry = ComponentDependencyRegistry.get_registry()
    component_registry.track_dependency(AggregatedSchemaConstraintsDependency)
    component_registry.track_dependency(SchemaAttributeRegexConstraintDependency)
    component_registry.track_dependency(SchemaAttributeUniqueConstraintDependency)
    component_registry.track_dependency(SchemaRelationshipOptionalConstraintDependency)
    component_registry.track_dependency(SchemaUniquenessConstraintDependency)
    component_registry.track_dependency(NodeAttributeUniquenessConstraintDependency)
    component_registry.track_dependency(NodeGroupedUniquenessConstraintDependency)
    component_registry.track_dependency(RelationshipCountConstraintDependency)
    component_registry.track_dependency(RelationshipProfilesKindConstraintDependency)
    component_registry.track_dependency(RelationshipPeerKindConstraintDependency)
    component_registry.track_dependency(NodeConstraintRunnerDependency)
    component_registry.track_dependency(NodeDeleteValidatorDependency)
    component_registry.track_dependency(IpamKindsGetterDependency)
    component_registry.track_dependency(IpamDiffParserDependency)
    component_registry.track_dependency(DiffCardinalityOneEnricherDependency)
    component_registry.track_dependency(DiffHierarchyEnricherDependency)
    component_registry.track_dependency(DiffAggregatedEnricherDependency)
    component_registry.track_dependency(DiffCalculatorDependency)
    component_registry.track_dependency(DiffCombinerDependency)
    component_registry.track_dependency(DiffRepositoryDependency)
    component_registry.track_dependency(DiffConflictTransfererDependency)
    component_registry.track_dependency(DiffCoordinatorDependency)
    component_registry.track_dependency(DiffDataCheckSynchronizerDependency)
    component_registry.track_dependency(DiffMergerDependency)
    return component_registry


def get_component_registry() -> ComponentDependencyRegistry:
    return ComponentDependencyRegistry.get_registry()
