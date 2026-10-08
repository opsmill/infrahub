import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getRunningRefsCheck } from "@/entities/repository/domain/use-cases/get-running-refs-check";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

export const RUNNING_REFS_CHECK_POLL_INTERVAL_MS = 2000;
export const IDLE_REFS_CHECK_POLL_INTERVAL_MS = 10_000;

export interface UseGetRunningRefsCheckParams {
  repositoryId: string;
}

export function useGetRunningRefsCheck({ repositoryId }: UseGetRunningRefsCheckParams) {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();
  const queryKey = repositoriesQueryKeys.runningRefsCheck({ repositoryId });

  const { data: runningTaskId = null } = useQuery({
    queryKey,
    queryFn: async () => {
      const taskId = await getRunningRefsCheck({ repositoryId });
      // Refetch the commit log once, when a check seen running is first seen ended.
      if (taskId === null && queryClient.getQueryData(queryKey)) {
        await queryClient.invalidateQueries({
          queryKey: repositoriesQueryKeys.repository({
            repositoryId,
            branchName: currentBranch.name,
          }),
        });
      }
      return taskId;
    },
    // Keeps polling while idle too, so a check started from another tab or by another user shows.
    refetchInterval: (query) =>
      query.state.data ? RUNNING_REFS_CHECK_POLL_INTERVAL_MS : IDLE_REFS_CHECK_POLL_INTERVAL_MS,
  });

  return { runningTaskId };
}
