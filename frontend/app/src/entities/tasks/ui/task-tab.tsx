import { useQueryState } from "nuqs";
import { useLocation } from "react-router";

import { TASK_TAB } from "@/config/constants";
import { QSP } from "@/config/qsp";

import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/ui/badge";
import { Spinner } from "@/shared/components/ui/spinner";

import { ObjectDetailsTab, type TaskTabProps } from "@/entities/nodes/object/ui/object-tabs";
import { useGetTaskCount } from "@/entities/tasks/domain/get-node-task-count/get-task-count.query";

export function ObjectTaskTab({ objectId, ...props }: TaskTabProps) {
  const { isPending, data: taskCount } = useGetTaskCount({ nodeId: objectId });
  const [qspTab] = useQueryState(QSP.TAB);

  const { pathname } = useLocation();

  return (
    <ObjectDetailsTab
      isActive={qspTab === TASK_TAB}
      to={constructPath(pathname, [{ name: QSP.TAB, value: TASK_TAB }])}
      {...props}
    >
      Tasks
      {isPending && <Spinner />}
      {!isPending && <Badge className="rounded-full font-medium text-gray-80">{taskCount}</Badge>}
    </ObjectDetailsTab>
  );
}
