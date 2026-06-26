import { Spinner } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { useGetRelationshipCount } from "@/entities/nodes/relationships/ui/queries/get-relationship-count.query";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { REPOSITORY_GROUP, REPOSITORY_OBJECTS_TAB } from "@/entities/repository/constants";

export interface RepositoryObjectsTabProps {
  objectKind: string;
  objectId: string;
}

export function RepositoryObjectsTab({ objectKind, objectId }: RepositoryObjectsTabProps) {
  const { isPending, data: objectsCount } = useGetRelationshipCount({
    objectId,
    objectKind: REPOSITORY_GROUP,
    relationshipName: "members",
    queryFilter: "repository__ids",
  });

  return (
    <LinkTab
      to={getObjectDetailsUrl(objectKind, objectId, undefined, REPOSITORY_OBJECTS_TAB)}
      scrollIntoViewOnActive
    >
      Objects
      {isPending && <Spinner />}
      {!isPending && (
        <Badge className="rounded-full font-medium text-gray-80">{objectsCount}</Badge>
      )}
    </LinkTab>
  );
}
