import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { TABLE_PAGE_SIZE } from "@/shared/utils/table-pagination";

import { TASK_STATE_CRASHED, TASK_STATE_FAILED } from "@/entities/tasks/domain/model/task";
import { getBranchTasks } from "@/entities/tasks/domain/use-cases/get-branch-tasks";
import { getTaskCountQueryOptions } from "@/entities/tasks/ui/queries/get-task-count.query";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

const BRANCH_TASKS_REFETCH_INTERVAL_MS = 10_000;

export function useGetBranchTasks({ branchName, page }: { branchName: string; page: number }) {
  const params = { branchName, offset: (page - 1) * TABLE_PAGE_SIZE, limit: TABLE_PAGE_SIZE };

  return useQuery({
    queryKey: tasksQueryKeys.branchList(params),
    queryFn: () => getBranchTasks(params),
    refetchInterval: page === 1 ? BRANCH_TASKS_REFETCH_INTERVAL_MS : false,
    placeholderData: keepPreviousData,
  });
}

export function useGetBranchFailedTaskCount({ branchName }: { branchName: string }) {
  return useQuery({
    ...getTaskCountQueryOptions({ branchName, state: [TASK_STATE_FAILED, TASK_STATE_CRASHED] }),
    refetchInterval: BRANCH_TASKS_REFETCH_INTERVAL_MS,
  });
}
