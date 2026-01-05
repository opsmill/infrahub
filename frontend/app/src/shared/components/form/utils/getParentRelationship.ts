import { getSchema } from "@/entities/schema/domain/get-schema";

export const getParentRelationship = (peer: string) => {
  const peerSchema = getSchema(peer);

  const parentRelationship = peerSchema?.schema?.relationships?.find(
    (rel) => rel.kind === "Parent"
  );

  return parentRelationship;
};
