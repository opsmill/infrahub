import { useMutationState, useQuery, useQueryClient } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type {
  CheckRemoteRefsParams,
  CheckRemoteRefsResult,
} from "@/entities/repository/domain/use-cases/check-remote-refs";
import { CHECK_REMOTE_REFS_MUTATION_KEY } from "@/entities/repository/ui/queries/check-remote-refs.mutation";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import { TASK_ONGOING_STATES } from "@/entities/tasks/domain/model/task";
import { checkTaskDetails } from "@/entities/tasks/domain/use-cases/check-task-details";

const REMOTE_CHECK_TASK_POLL_INTERVAL_MS = 2000;

const isCheckRemoteRefsParams = (value: unknown): value is CheckRemoteRefsParams =>
  typeof value === "object" && value !== null && "repositoryId" in value && "branchName" in value;

const isCheckRemoteRefsResult = (value: unknown): value is CheckRemoteRefsResult =>
  typeof value === "object" && value !== null && "ok" in value;

export interface UseGetRemoteCheckTaskParams {
  repositoryId: string;
}

export interface RemoteCheckTask {
  isSubmitting: boolean;
  isOngoing: boolean;
  taskId: string | null;
}

export function useGetRemoteCheckTask({
  repositoryId,
}: UseGetRemoteCheckTaskParams): RemoteCheckTask {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();

  // Read from the mutation cache rather than component state, so a check started before the tab
  // remounted is still followed.
  const checks = useMutationState({
    filters: { mutationKey: CHECK_REMOTE_REFS_MUTATION_KEY },
    select: ({ state }) => ({
      variables: isCheckRemoteRefsParams(state.variables) ? state.variables : undefined,
      status: state.status,
      data: isCheckRemoteRefsResult(state.data) ? state.data : undefined,
    }),
  });
  const checksOfThisRepository = checks.filter(
    ({ variables }) =>
      variables?.repositoryId === repositoryId && variables.branchName === currentBranch.name
  );
  const latest = checksOfThisRepository.at(-1);
  const taskId = (latest?.status === "success" && latest.data?.taskId) || null;

  const { data: ongoingCount } = useQuery({
    queryKey: repositoriesQueryKeys.remoteCheckTask({ taskId: taskId ?? "" }),
    queryFn: async ({ queryKey }) => {
      const count = await checkTaskDetails({ ids: [taskId], state: TASK_ONGOING_STATES });
      // Refetch the commit log once, when the task is first seen ended, not on every later refetch.
      if (count === 0 && queryClient.getQueryData(queryKey) !== 0) {
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
    refetchOnWindowFocus: false,
    refetchInterval: (query) =>
      query.state.data === 0 ? false : REMOTE_CHECK_TASK_POLL_INTERVAL_MS,
  });

  return {
    isSubmitting: latest?.status === "pending",
    // A failed poll keeps the check ongoing: only a confirmed count of zero ends it.
    isOngoing: taskId !== null && ongoingCount !== 0,
    taskId,
  };
}
