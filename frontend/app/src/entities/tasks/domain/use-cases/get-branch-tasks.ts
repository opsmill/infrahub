import { getTaskListFromApi } from "@/entities/tasks/api/get-task-list-from-api";
import type { BranchTasksPage } from "@/entities/tasks/domain/model/branch-task";

export type GetBranchTasksParams = { branchName: string; offset: number; limit: number };

export type GetBranchTasksResult = BranchTasksPage;

export const getBranchTasks = async ({
  branchName,
  offset,
  limit,
}: GetBranchTasksParams): Promise<GetBranchTasksResult> => {
  const { data, errors } = await getTaskListFromApi({ branchName, offset, limit });

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

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
