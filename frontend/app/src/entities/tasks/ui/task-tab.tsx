import { useQueryState } from "nuqs";
import { useLocation } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/ui/badge";
import { Spinner } from "@/shared/components/ui/spinner";
import { TASK_TAB } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import { ObjectDetailsTab, type TaskTabProps } from "@/entities/nodes/object/ui/object-tabs";
import { useGetTaskCount } from "@/entities/tasks/ui/queries/get-task-count.query";

export function ObjectTaskTab({ objectId, ...props }: TaskTabProps) {
  const { pathname } = useLocation();
  const [qspTab] = useQueryState(QSP.TAB);
  const { isPending, data: taskCount } = useGetTaskCount({ relatedNodeIds: [objectId] });

  return (
    <ObjectDetailsTab
      isActive={qspTab === TASK_TAB}
      to={constructPath(pathname, [{ name: QSP.TAB, value: TASK_TAB }])}
      {...props}
    >
      Tasks
      {isPending ? (
        <Spinner />
      ) : (
        <Badge className="rounded-full font-medium text-gray-80">{taskCount}</Badge>
      )}
    </ObjectDetailsTab>
  );
}
