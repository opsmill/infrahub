import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import { TASK_ONGOING_STATES } from "@/entities/tasks/domain/model/task";
import { checkTaskDetails } from "@/entities/tasks/domain/use-cases/check-task-details";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

const REMOTE_CHECK_TASK_POLL_INTERVAL_MS = 2000;

export interface UseRemoteCheckTaskParams {
  repositoryId: string;
  taskId: string | null;
}

// Keyed outside the repository key: the commit-log refetch it triggers would otherwise invalidate it.
export function useRemoteCheckTask({ repositoryId, taskId }: UseRemoteCheckTaskParams) {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();

  const { data: ongoingCount, isError } = useQuery({
    queryKey: [...tasksQueryKeys.all, "repository-remote-check", taskId] as const,
    queryFn: async () => {
      const count = await checkTaskDetails({ ids: [taskId], state: TASK_ONGOING_STATES });
      if (count === 0) {
        await queryClient.invalidateQueries({
          queryKey: repositoriesQueryKeys.repository({
            repositoryId,
            branchName: currentBranch.name,
          }),
        });
      }
      return count;
    },
    enabled: taskId !== null,
    refetchInterval: (query) =>
      query.state.data === 0 ? false : REMOTE_CHECK_TASK_POLL_INTERVAL_MS,
  });

  return { isOngoing: taskId !== null && !isError && ongoingCount !== 0 };
}
