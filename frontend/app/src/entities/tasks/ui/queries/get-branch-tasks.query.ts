import { queryOptions, useQuery } from "@tanstack/react-query";

import { pollWhileHealthy, retryBackgroundQuery } from "@/shared/api/background-query";
import { useCountClampedQuery } from "@/shared/hooks/use-count-clamped-query";

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
    retry: retryBackgroundQuery,
    refetchInterval: (query) =>
      pollWhileHealthy(params.offset === 0, BRANCH_TASKS_REFETCH_INTERVAL_MS, query),
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[2].branchName === params.branchName ? previousData : undefined,
  });
}

export interface UseGetBranchTasksParams {
  branchName: string;
  page: number;
  pageSize: number;
}

export function useGetBranchTasks({ branchName, page, pageSize }: UseGetBranchTasksParams) {
  return useCountClampedQuery({ page, pageSize }, (offset) =>
    getBranchTasksQueryOptions({ branchName, offset, limit: pageSize })
  );
}

// FAILED only: the Tasks page filters on a single state, and the count must match what its link opens.
export function getBranchFailedTaskCountQueryOptions({ branchName }: { branchName: string }) {
  const params = { branchName, state: [TASK_STATE_FAILED] };

  return queryOptions({
    ...getTaskCountQueryOptions(params),
    queryFn: () => getTaskCount(params, { silenceErrors: true }),
    retry: retryBackgroundQuery,
    refetchInterval: (query) => pollWhileHealthy(true, BRANCH_TASKS_REFETCH_INTERVAL_MS, query),
  });
}

export function useGetBranchFailedTaskCount(params: { branchName: string }) {
  return useQuery(getBranchFailedTaskCountQueryOptions(params));
}
