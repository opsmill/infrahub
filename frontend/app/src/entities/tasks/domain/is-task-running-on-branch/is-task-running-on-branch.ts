import { getBranchTaskStatusFromApi } from "@/entities/tasks/api/get-branch-task-status-from-api";

export type IsTaskRunningOnBranch = (branch: string) => Promise<boolean>;

export const isTaskRunningOnBranch: IsTaskRunningOnBranch = async (branch: string) => {
  const { data, error } = await getBranchTaskStatusFromApi(branch);

  if (error) throw error;

  return !!data?.InfrahubTaskBranchStatus?.count && data.InfrahubTaskBranchStatus.count > 0;
};
