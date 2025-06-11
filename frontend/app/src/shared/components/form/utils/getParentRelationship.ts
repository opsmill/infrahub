import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { store } from "@/shared/stores";

export const getParentRelationship = (peer?: string) => {
  if (!peer) return;

  const nodes = store.get(nodeSchemasAtom);
  const peerSchema = nodes.find((schema) => schema.kind === peer);
  const parentRelationship = peerSchema?.relationships?.find((rel) => rel.kind === "Parent");

  return parentRelationship;
};
