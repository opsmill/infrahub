import { useProposedChangeOutlet } from "@/entities/proposed-changes/ui/routing/use-proposed-change-outlet";
import { TaskItems } from "@/entities/tasks/ui/task-items";

export function Component() {
  const { proposedChangeData } = useProposedChangeOutlet();
  return <TaskItems relatedNodeId={proposedChangeData.id} />;
}
