import { queryOptions, useQuery } from "@tanstack/react-query";

import { ERROR_CODES } from "@/shared/api/errors";
import { hasOnlyThrownCatalogueCode } from "@/shared/api/graphql/error-handling";
import { keepPreviousDataWithin } from "@/shared/api/keep-previous-data-within";
import { getOffset } from "@/shared/utils/table-pagination";

import { TASK_STATE_FAILED } from "@/entities/tasks/domain/model/task";
import type { TaskListPage } from "@/entities/tasks/domain/model/task-list-item";
import {
  type GetBranchTasksParams,
  getBranchTasks,
} from "@/entities/tasks/domain/use-cases/get-branch-tasks";
import { getTaskCount } from "@/entities/tasks/domain/use-cases/get-task-count";
import { getTaskCountQueryOptions } from "@/entities/tasks/ui/queries/get-task-count.query";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

const BRANCH_TASKS_REFETCH_INTERVAL_MS = 10_000;
// A failed poll retries at this pace so the card recovers on its own without hammering the API.
const BRANCH_TASKS_ERROR_REFETCH_INTERVAL_MS = 60_000;

const pollTasks = (state: { status: string; error: Error | null }): number | false => {
  if (hasOnlyThrownCatalogueCode(state.error, ERROR_CODES.PERMISSION_DENIED)) return false;
  return state.status === "error"
    ? BRANCH_TASKS_ERROR_REFETCH_INTERVAL_MS
    : BRANCH_TASKS_REFETCH_INTERVAL_MS;
};

export function getBranchTasksQueryOptions(params: GetBranchTasksParams) {
  return queryOptions({
    queryKey: tasksQueryKeys.branchList(params),
    queryFn: () => getBranchTasks(params, { silenceErrors: true }),
    // Only the first page gets new tasks as they start.
    refetchInterval: ({ state }) => (params.offset === 0 ? pollTasks(state) : false),
    placeholderData: keepPreviousDataWithin(
      tasksQueryKeys.branchListOnBranch({ branchName: params.branchName }),
      (page: TaskListPage) => page.tasks.length > 0
    ),
  });
}

interface UseGetBranchTasksParams {
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
    refetchInterval: ({ state }) => pollTasks(state),
  });
}

export function useGetBranchFailedTaskCount(params: { branchName: string }) {
  return useQuery(getBranchFailedTaskCountQueryOptions(params));
}
