import type { ModelSchema } from "@/entities/schema/domain/model/types";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

export function canDissociateRelationship({
  relationshipName,
  parentSchema,
  relationshipsCount,
}: {
  relationshipName: string;
  parentSchema: ModelSchema;
  relationshipsCount: number;
}): boolean {
  const parentToPeerRelationship = parentSchema.relationships?.find((relationship) => {
    return relationship.name === relationshipName;
  });
  if (!parentToPeerRelationship) {
    return false;
  }

  const { schema: peerSchema } = getSchema(parentToPeerRelationship.peer);

  const peerToParentRelationship = peerSchema?.relationships?.find((relationship) => {
    const isValidKind = isOfKind(relationship.peer, parentSchema);

    if (!isValidKind) {
      return false;
    }

    if (parentToPeerRelationship.direction === "bidirectional") {
      return relationship.direction === "bidirectional";
    }

    if (parentToPeerRelationship.direction === "inbound") {
      return relationship.direction === "outbound";
    }

    return relationship.direction === "inbound";
  });

  const minimumRequiredCount = parentToPeerRelationship.min_count || 1;
  const isParentRelationshipOptional = parentToPeerRelationship.optional;
  const hasMoreThanMinimumRequired = relationshipsCount > minimumRequiredCount;

  if (!peerToParentRelationship) {
    return isParentRelationshipOptional || hasMoreThanMinimumRequired;
  }

  const isPeerRelationshipOptional = peerToParentRelationship.optional;

  if (isParentRelationshipOptional && isPeerRelationshipOptional) {
    return true;
  }

  if (!isParentRelationshipOptional) {
    return hasMoreThanMinimumRequired;
  }

  return isPeerRelationshipOptional;
}
