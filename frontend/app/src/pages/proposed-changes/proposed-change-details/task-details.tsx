import { Icon } from "@iconify-icon/react";
import { Link, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";

import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };

  return (
    <div>
      <div className="flex bg-white text-sm">
        <Link
          to={constructPath(`/proposed-changes/${proposedChangeId}/tasks`)}
          className="flex items-center p-2"
        >
          <Icon icon="mdi:chevron-left" />
          All tasks
        </Link>
      </div>

      <TaskItemDetails />
    </div>
  );
}
