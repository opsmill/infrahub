import { QSP } from "@/config/qsp";
import { ObjectDetailsTab, TaskTabProps } from "@/entities/nodes/object/ui/object-tabs";
import { REPOSITORY_OBJECTS_TAB } from "@/entities/repository/constant";
import { useGetRepositoryObjectsCount } from "@/entities/repository/domain/get-repository-objects-count.query";
import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/ui/badge";
import { Spinner } from "@/shared/components/ui/spinner";
import { useLocation } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";

export function RepositoryObjectsTab({ objectId, ...props }: TaskTabProps) {
  const { isPending, data: objectsCount } = useGetRepositoryObjectsCount({ nodeId: objectId });
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);

  const { pathname } = useLocation();

  return (
    <ObjectDetailsTab
      isActive={qspTab === REPOSITORY_OBJECTS_TAB}
      to={constructPath(pathname, [{ name: QSP.TAB, value: REPOSITORY_OBJECTS_TAB }])}
      {...props}
    >
      Objects
      {isPending && <Spinner />}
      <Badge className="font-medium rounded-full text-gray-80">{objectsCount}</Badge>
    </ObjectDetailsTab>
  );
}
