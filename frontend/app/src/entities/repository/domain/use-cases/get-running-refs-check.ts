import { getRunningRefsCheckFromApi } from "@/entities/repository/api/get-running-refs-check-from-api";
import { READONLY_REPOSITORY_CHECK_REFS_WORKFLOW } from "@/entities/repository/domain/model/repository";
import { TASK_ONGOING_STATES } from "@/entities/tasks/domain/model/task";

export interface GetRunningRefsCheckParams {
  repositoryId: string;
}

export type GetRunningRefsCheck = (params: GetRunningRefsCheckParams) => Promise<string | null>;

// Only on-demand checks run as a task of their own; a scheduled check runs inside the fleet-wide
// task and is not found here.
export const getRunningRefsCheck: GetRunningRefsCheck = async ({ repositoryId }) => {
  const { data } = await getRunningRefsCheckFromApi({
    repositoryId,
    workflow: [READONLY_REPOSITORY_CHECK_REFS_WORKFLOW],
    state: TASK_ONGOING_STATES,
  });

  return data.InfrahubTask.edges[0]?.node?.id ?? null;
};
