import { useQueryState } from "nuqs";
import { useLocation } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/ui/badge";
import { Spinner } from "@/shared/components/ui/spinner";
import { QSP } from "@/shared/config/qsp";

import { ObjectDetailsTab, type TaskTabProps } from "@/entities/nodes/object/ui/object-tabs";
import { useGetRelationshipCount } from "@/entities/nodes/relationships/domain/get-relationship-count/get-relationship-count.query";
import { REPOSITORY_GROUP, REPOSITORY_OBJECTS_TAB } from "@/entities/repository/constants";

export function RepositoryObjectsTab({ objectId, ...props }: TaskTabProps) {
  const { isPending, data: objectsCount } = useGetRelationshipCount({
    objectId,
    objectKind: REPOSITORY_GROUP,
    relationshipName: "members",
    queryFilter: "repository__ids",
  });
  const [qspTab] = useQueryState(QSP.TAB);

  const { pathname } = useLocation();

  return (
    <ObjectDetailsTab
      isActive={qspTab === REPOSITORY_OBJECTS_TAB}
      to={constructPath(pathname, [{ name: QSP.TAB, value: REPOSITORY_OBJECTS_TAB }])}
      {...props}
    >
      Objects
      {isPending && <Spinner />}
      {!isPending && (
        <Badge className="rounded-full font-medium text-gray-80">{objectsCount ?? 0}</Badge>
      )}
    </ObjectDetailsTab>
  );
}
