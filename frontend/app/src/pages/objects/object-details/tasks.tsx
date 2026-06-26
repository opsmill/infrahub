import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/object-details/use-object-details-outlet";
import { TaskItems } from "@/entities/tasks/ui/task-items";

export function Component() {
  const { objectData } = useObjectDetailsOutlet();
  return <TaskItems relatedNodeId={objectData.id} />;
}
