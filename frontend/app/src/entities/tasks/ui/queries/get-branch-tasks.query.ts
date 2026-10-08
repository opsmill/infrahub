import { queryOptions, useQuery } from "@tanstack/react-query";

import { keepPreviousDataWithin } from "@/shared/api/keep-previous-data-within";
import { getOffset } from "@/shared/utils/table-pagination";

import { TASK_STATE_FAILED } from "@/entities/tasks/domain/model/task";
import {
  type GetBranchTasksParams,
  getBranchTasks,
} from "@/entities/tasks/domain/use-cases/get-branch-tasks";
import { getTaskCount } from "@/entities/tasks/domain/use-cases/get-task-count";
import { getTaskCountQueryOptions } from "@/entities/tasks/ui/queries/get-task-count.query";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

const BRANCH_TASKS_REFETCH_INTERVAL_MS = 10_000;

export function getBranchTasksQueryOptions(params: GetBranchTasksParams) {
  return queryOptions({
    queryKey: tasksQueryKeys.branchList(params),
    queryFn: () => getBranchTasks(params),
    // Only the first page gets new tasks as they start.
    refetchInterval: params.offset === 0 ? BRANCH_TASKS_REFETCH_INTERVAL_MS : false,
    placeholderData: keepPreviousDataWithin(
      tasksQueryKeys.branchListOnBranch({ branchName: params.branchName })
    ),
  });
}

export interface UseGetBranchTasksParams {
  branchName: string;
  page: number;
  pageSize: number;
}

export function useGetBranchTasks({ branchName, page, pageSize }: UseGetBranchTasksParams) {
  return useQuery(
    getBranchTasksQueryOptions({ branchName, offset: getOffset(page, pageSize), limit: pageSize })
  );
}

// FAILED only: the Tasks page filters on a single state, and the count must match what its link opens.
export function getBranchFailedTaskCountQueryOptions({ branchName }: { branchName: string }) {
  const params = { branchName, state: [TASK_STATE_FAILED] };

  return queryOptions({
    ...getTaskCountQueryOptions(params),
    queryFn: () => getTaskCount(params, { silenceErrors: true }),
    refetchInterval: BRANCH_TASKS_REFETCH_INTERVAL_MS,
  });
}

export function useGetBranchFailedTaskCount(params: { branchName: string }) {
  return useQuery(getBranchFailedTaskCountQueryOptions(params));
}
