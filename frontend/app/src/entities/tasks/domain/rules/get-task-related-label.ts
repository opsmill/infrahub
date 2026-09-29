import type { BranchTask } from "@/entities/tasks/domain/model/branch-task";

export function getTaskRelatedLabel(
  task: Pick<BranchTask, "relatedNodes">,
  repositoriesById: ReadonlyMap<string, string>,
  getKindLabel: (kind: string) => string = (kind) => kind
): string {
  const [firstNode] = task.relatedNodes;
  if (!firstNode) return "This branch";

  const repositoryName = task.relatedNodes
    .map(({ id }) => repositoriesById.get(id))
    .find((name) => name !== undefined);

  return repositoryName ?? getKindLabel(firstNode.kind);
}
