import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";

import { useProposedChangeOutlet } from "@/entities/proposed-changes/ui/use-proposed-change-outlet";
import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";

export function Component() {
  const { proposedChangeData } = useProposedChangeOutlet();

  return (
    <div>
      <div className="flex bg-white text-sm">
        <Link
          to={constructPath(`/proposed-changes/${proposedChangeData.id}/tasks`)}
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
