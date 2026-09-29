import { getTaskListFromApi } from "@/entities/tasks/api/get-task-list-from-api";
import type { BranchTasksPage } from "@/entities/tasks/domain/model/branch-task";

export type GetBranchTasksParams = { branchName: string; offset: number; limit: number };

export const getBranchTasks = async ({
  branchName,
  offset,
  limit,
}: GetBranchTasksParams): Promise<BranchTasksPage> => {
  const { data } = await getTaskListFromApi({ branchName, offset, limit });

  const tasks = data.InfrahubTask.edges.flatMap(({ node }) =>
    node
      ? [
          {
            id: node.id,
            title: node.title,
            state: node.state ?? null,
            workflow: node.workflow ?? null,
            relatedNodes: (node.related_nodes ?? []).filter((n) => !!n),
            updatedAt: node.updated_at,
          },
        ]
      : []
  );

  return { tasks, count: data.InfrahubTask.count };
};
