import { keepPreviousData, queryOptions, useQuery } from "@tanstack/react-query";

import { TABLE_PAGE_SIZE, toPageNumber } from "@/shared/utils/table-pagination";

import { TASK_STATE_FAILED } from "@/entities/tasks/domain/model/task";
import { getBranchTasks } from "@/entities/tasks/domain/use-cases/get-branch-tasks";
import { getTaskCountQueryOptions } from "@/entities/tasks/ui/queries/get-task-count.query";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

const BRANCH_TASKS_REFETCH_INTERVAL_MS = 10_000;

export interface GetBranchTasksQueryParams {
  branchName: string;
  page: number;
}

export function getBranchTasksQueryOptions({ branchName, page }: GetBranchTasksQueryParams) {
  const currentPage = toPageNumber(page);
  const params = {
    branchName,
    offset: (currentPage - 1) * TABLE_PAGE_SIZE,
    limit: TABLE_PAGE_SIZE,
  };

  return queryOptions({
    queryKey: tasksQueryKeys.branchList(params),
    queryFn: () => getBranchTasks(params),
    refetchInterval: currentPage === 1 ? BRANCH_TASKS_REFETCH_INTERVAL_MS : false,
    placeholderData: keepPreviousData,
  });
}

export function useGetBranchTasks(params: GetBranchTasksQueryParams) {
  return useQuery(getBranchTasksQueryOptions(params));
}

// FAILED only: the Tasks page filters on a single state, and the count must match what its link opens.
export function getBranchFailedTaskCountQueryOptions({ branchName }: { branchName: string }) {
  return queryOptions({
    ...getTaskCountQueryOptions({ branchName, state: [TASK_STATE_FAILED] }),
    refetchInterval: BRANCH_TASKS_REFETCH_INTERVAL_MS,
  });
}

export function useGetBranchFailedTaskCount(params: { branchName: string }) {
  return useQuery(getBranchFailedTaskCountQueryOptions(params));
}
