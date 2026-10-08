import { queryOptions, skipToken } from "@tanstack/react-query";

import { isTaskFinished } from "@/entities/tasks/domain/use-cases/is-task-finished";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

const TASK_FINISHED_REFETCH_INTERVAL_MS = 5000;
// A task the server never lists, such as a purged one, would otherwise be checked for as long as the page stays open.
const TASK_FINISHED_MAX_CHECKS = 360;

export function isTaskFinishedQueryOptions({ taskId }: { taskId: string | null }) {
  return queryOptions({
    queryKey: tasksQueryKeys.finished({ taskId: taskId ?? "" }),
    queryFn: taskId ? () => isTaskFinished({ taskId }) : skipToken,
    // A failed check keeps polling too, because the task can still end after it.
    refetchInterval: ({ state }) =>
      state.data || state.dataUpdateCount + state.errorUpdateCount >= TASK_FINISHED_MAX_CHECKS
        ? false
        : TASK_FINISHED_REFETCH_INTERVAL_MS,
  });
}
