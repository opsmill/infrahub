import { useParams } from "react-router";

import { TaskItems } from "@/entities/tasks/ui/task-items";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };
  return <TaskItems relatedNodeId={proposedChangeId} />;
}
