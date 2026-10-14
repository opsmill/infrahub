import type { TaskListItem } from "@/entities/tasks/domain/model/task-list-item";

export function getRelatedNodeIds(tasks: Pick<TaskListItem, "relatedNodes">[]): string[] {
  return [...new Set(tasks.flatMap(({ relatedNodes }) => relatedNodes.map(({ id }) => id)))].sort();
}
