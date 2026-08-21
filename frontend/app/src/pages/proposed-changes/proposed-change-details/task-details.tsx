import { Link } from "react-router";

import { Icon } from "@/shared/components/display/icon";

import { getProposedChangeDetailsUrl } from "@/entities/proposed-changes/ui/routing/proposed-change-urls";
import { useProposedChangeOutlet } from "@/entities/proposed-changes/ui/routing/use-proposed-change-outlet";
import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";

export function Component() {
  const { proposedChangeData } = useProposedChangeOutlet();

  return (
    <div>
      <div className="flex bg-content text-sm">
        <Link
          to={getProposedChangeDetailsUrl(proposedChangeData.id, "tasks")}
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
