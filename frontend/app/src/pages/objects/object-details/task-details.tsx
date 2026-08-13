import { Link } from "react-router";

import { Icon } from "@/shared/components/display/icon";
import { useRequiredParams } from "@/shared/hooks/use-required-params";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/routing/use-object-details-outlet";
import { useGetTaskDetailsTitle } from "@/entities/tasks/ui/queries/get-task-details-title.query";
import { TaskActions } from "@/entities/tasks/ui/task-actions";
import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";

export function Component() {
  const { objectData } = useObjectDetailsOutlet();
  const { taskId } = useRequiredParams("taskId");
  const { data: taskData } = useGetTaskDetailsTitle({ ids: [taskId] });

  return (
    <>
      <div className="flex items-center bg-white text-sm">
        <Link
          to={getObjectDetailsUrl(objectData.__typename, objectData.id, undefined, "tasks")}
          className="flex items-center p-2"
        >
          <Icon icon="mdi:chevron-left" />
          All tasks
        </Link>

        {taskData && <TaskActions task={taskData} className="ml-auto p-2" />}
      </div>

      <TaskItemDetails />
    </>
  );
}
