import { RelationshipTable } from "@/entities/nodes/relationships/ui/relationship-table/relationship-table";
import { REPOSITORY_GROUP } from "@/entities/repository/constant";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface RepositoryObjectsManagerProps {
  parentNodeId: string;
}
export function RepositoryObjectsManager({ parentNodeId }: RepositoryObjectsManagerProps) {
  const { schema } = useSchema(REPOSITORY_GROUP);

  const membersRelationship = schema?.relationships?.find((relationship) => {
    return relationship.name === "members";
  });

  const { schema: relationshipSchema } = useSchema(membersRelationship?.peer);

  return (
    <RelationshipTable
      parentKind={REPOSITORY_GROUP}
      parentId={parentNodeId}
      relationshipName={"members"}
      relationshipSchema={relationshipSchema}
    />
  );
}
