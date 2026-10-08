import type { TaskListItem } from "@/entities/tasks/domain/model/task-list-item";

export function getTaskRelatedLabel(
  task: Pick<TaskListItem, "relatedNodes">,
  repositoriesById: ReadonlyMap<string, string>,
  getKindLabel: (kind: string) => string = (kind) => kind,
  emptyLabel = "—"
): string {
  const [firstNode] = task.relatedNodes;
  if (!firstNode) return emptyLabel;

  const repositoryName = task.relatedNodes
    .map(({ id }) => repositoriesById.get(id))
    .find((name) => name !== undefined);

  return repositoryName ?? getKindLabel(firstNode.kind);
}
