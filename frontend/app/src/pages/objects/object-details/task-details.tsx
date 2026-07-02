import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/routing/use-object-details-outlet";
import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";

export function Component() {
  const { objectData } = useObjectDetailsOutlet();

  return (
    <>
      <div className="flex bg-white text-sm">
        <Link
          to={getObjectDetailsUrl(objectData.__typename, objectData.id, undefined, "tasks")}
          className="flex items-center p-2"
        >
          <Icon icon="mdi:chevron-left" />
          All tasks
        </Link>
      </div>

      <TaskItemDetails />
    </>
  );
}
