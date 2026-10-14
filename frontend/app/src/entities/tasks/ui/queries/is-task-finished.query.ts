import { type QueryState, queryOptions, skipToken } from "@tanstack/react-query";

import { isTaskFinished } from "@/entities/tasks/domain/use-cases/is-task-finished";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

const TASK_FINISHED_REFETCH_INTERVAL_MS = 5000;
// A task the server never lists, such as a purged one, would otherwise be checked for as long as the page stays open.
const TASK_FINISHED_MAX_CHECKS = 360;

function isDoneChecking(state: QueryState<boolean>): boolean {
  return (
    state.data === true ||
    state.dataUpdateCount + state.errorUpdateCount >= TASK_FINISHED_MAX_CHECKS
  );
}

export function isTaskFinishedQueryOptions({ taskId }: { taskId: string | null }) {
  return queryOptions({
    queryKey: tasksQueryKeys.finished({ taskId: taskId ?? "" }),
    queryFn: taskId ? () => isTaskFinished({ taskId }) : skipToken,
    // A failed check keeps polling too, because the task can still end after it.
    refetchInterval: ({ state }) =>
      isDoneChecking(state) ? false : TASK_FINISHED_REFETCH_INTERVAL_MS,
    // Once done, a window focus, reconnect or remount must not check the task again.
    staleTime: ({ state }) => (isDoneChecking(state) ? Number.POSITIVE_INFINITY : 0),
  });
}
