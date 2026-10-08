import type { ScopeCandidate } from "@/entities/resource-manager/domain/model/scope-candidate";
import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";

function getAttributeUnavailableReason(
  attribute: AttributeSchema,
  nodeAttribute: string
): string | undefined {
  if (attribute.name === nodeAttribute) return "This is the attribute the pool allocates";
  if (attribute.kind === ATTRIBUTE_KIND.LIST) return "List attributes can't be used";
  if (attribute.kind === ATTRIBUTE_KIND.JSON) return "JSON attributes can't be used";
  if (attribute.optional) return "Optional";
  return undefined;
}

// Mirrors the backend uniqueness-constraint rule: only a required relationship of cardinality one is accepted.
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

  const relationships = (schema.relationships ?? []).map((relationship) =>
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
