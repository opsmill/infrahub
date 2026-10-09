import type { RelationshipKind } from "@/entities/nodes/object/domain/model/node";
import type { ScopeCandidate } from "@/entities/resource-manager/domain/model/scope-candidate";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";

// Infrahub adds these to every kind and they never identify a scope; Hierarchy is kept because a required `parent` can.
const SYSTEM_RELATIONSHIP_KINDS: RelationshipKind[] = ["Group", "Profile", "Template"];

function getAttributeUnavailableReason(
  attribute: AttributeSchema,
  nodeAttribute: string
): string | undefined {
  if (attribute.name === nodeAttribute) return "This is the attribute the pool allocates";
  if (attribute.optional) return "Optional";
  return undefined;
}

// Only a required relationship of cardinality one can identify a scope.
function getRelationshipUnavailableReason(relationship: RelationshipSchema): string | undefined {
  if (relationship.cardinality === "many") return "Relationships of cardinality many can't be used";
  if (relationship.optional) return "Optional";
  return undefined;
}

function toCandidate(
  base: Omit<ScopeCandidate, "unavailableReason">,
  unavailableReason: string | undefined
): ScopeCandidate {
  return unavailableReason ? { ...base, unavailableReason } : base;
}

/** Lists only the kind's own fields, as bare names, because the scope cannot reach into a related node. */
export function getScopeCandidates(schema: ModelSchema, nodeAttribute: string): ScopeCandidate[] {
  const attributes = (schema.attributes ?? []).map((attribute) =>
    toCandidate(
      {
        name: attribute.name,
        label: attribute.label ?? attribute.name,
        type: "attribute",
        detail: attribute.kind,
      },
      getAttributeUnavailableReason(attribute, nodeAttribute)
    )
  );

  const relationships = (schema.relationships ?? [])
    .filter(({ kind }) => !SYSTEM_RELATIONSHIP_KINDS.includes(kind))
    .map((relationship) =>
      toCandidate(
        {
          name: relationship.name,
          label: relationship.label ?? relationship.name,
          type: "relationship",
          detail: relationship.peer,
        },
        getRelationshipUnavailableReason(relationship)
      )
    );

  return [...attributes, ...relationships];
}
