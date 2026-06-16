import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { Spinner } from "@/shared/components/ui/spinner";

import { RelationshipTable } from "@/entities/nodes/relationships/ui/relationship-table/relationship-table";
import { REPOSITORY_GROUP } from "@/entities/repository/constants";
import { useGetRepositoryGroup } from "@/entities/repository/ui/queries/get-repository-group.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface RepositoryObjectsManagerProps {
  parentNodeId: string;
}
export function RepositoryObjectsManager({ parentNodeId }: RepositoryObjectsManagerProps) {
  const { schema } = useSchema(REPOSITORY_GROUP, { throwIfNotFound: true });
  const { isPending, data, error } = useGetRepositoryGroup({ nodeId: parentNodeId });

  const membersRelationship = schema.relationships?.find((relationship) => {
    return relationship.name === "members";
  });

  const { schema: relationshipSchema } = useSchema(membersRelationship?.peer);

  if (isPending) {
    return <Spinner />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (!data.id) {
    return <NoDataFound message="No objects found for this repository" />;
  }

  return (
    <RelationshipTable
      parentKind={REPOSITORY_GROUP}
      parentId={data.id}
      relationshipName={"members"}
      relationshipSchema={relationshipSchema}
    />
  );
}
