import { RelationshipTable } from "@/entities/nodes/relationships/ui/relationship-table/relationship-table";
import { REPOSITORY_GROUP } from "@/entities/repository/constant";
import { useGetRepositoryGroup } from "@/entities/repository/domain/get-repository-group.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { Spinner } from "@/shared/components/ui/spinner";

export interface RepositoryObjectsManagerProps {
  parentNodeId: string;
}
export function RepositoryObjectsManager({ parentNodeId }: RepositoryObjectsManagerProps) {
  const { schema } = useSchema(REPOSITORY_GROUP);
  const { isPending, data: repositoryId } = useGetRepositoryGroup({ nodeId: parentNodeId });

  const membersRelationship = schema?.relationships?.find((relationship) => {
    return relationship.name === "members";
  });

  const { schema: relationshipSchema } = useSchema(membersRelationship?.peer);

  if (isPending) {
    return <Spinner />;
  }

  return (
    <RelationshipTable
      parentKind={REPOSITORY_GROUP}
      parentId={repositoryId}
      relationshipName={"members"}
      relationshipSchema={relationshipSchema}
    />
  );
}
