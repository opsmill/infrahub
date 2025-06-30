import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export const getParentRelationship = (peer?: string) => {
  const peerSchema = useSchema(peer);

  const parentRelationship = peerSchema?.schema?.relationships?.find(
    (rel) => rel.kind === "Parent"
  );

  return parentRelationship;
};
