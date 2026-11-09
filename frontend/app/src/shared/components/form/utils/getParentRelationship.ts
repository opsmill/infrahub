import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

export const getParentRelationship = (peer: string): RelationshipSchema | null => {
  const peerSchema = getSchema(peer);

  const parentRelationship = peerSchema?.schema?.relationships?.find(
    (rel) => rel.kind === "Parent"
  );

  return parentRelationship ?? null;
};
