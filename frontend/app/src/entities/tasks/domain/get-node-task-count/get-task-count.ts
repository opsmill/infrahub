import type { BranchContextParams } from "@/shared/api/types";

import { getTaskCountFromApi } from "@/entities/tasks/api/get-task-count-from-api";

export interface GetTaskCountParams extends BranchContextParams {
  nodeId: string;
}

export type GetTaskCount = (params: GetTaskCountParams) => Promise<number>;

export const getTaskCount: GetTaskCount = async ({ branchName, nodeId }) => {
  const { data } = await getTaskCountFromApi({
    branchName,
    nodeIds: [nodeId],
  });

  return data.InfrahubTask.count;
};
