import { skipToken, useMutationState, useQuery, useQueryClient } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type {
  CheckRemoteRefsParams,
  CheckRemoteRefsResult,
} from "@/entities/repository/domain/use-cases/check-remote-refs";
import {
  type GetRemoteCheckTaskResult,
  getRemoteCheckTask,
} from "@/entities/repository/domain/use-cases/get-remote-check-task";
import { CHECK_REMOTE_REFS_MUTATION_KEY } from "@/entities/repository/ui/queries/check-remote-refs.mutation";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";

const REMOTE_CHECK_TASK_POLL_INTERVAL_MS = 2000;

const isCheckRemoteRefsParams = (value: unknown): value is CheckRemoteRefsParams =>
  typeof value === "object" && value !== null && "repositoryId" in value && "branchName" in value;

const isCheckRemoteRefsResult = (value: unknown): value is CheckRemoteRefsResult =>
  typeof value === "string";

export interface UseGetRemoteCheckTaskParams {
  repositoryId: string;
}

export function useGetRemoteCheckTask({ repositoryId }: UseGetRemoteCheckTaskParams) {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();

  // Read from the mutation cache rather than the button's own mutation, which a change of commit-log
  // state remounts.
  const checks = useMutationState({
    filters: { mutationKey: CHECK_REMOTE_REFS_MUTATION_KEY },
    select: ({ state }) => ({
      variables: isCheckRemoteRefsParams(state.variables) ? state.variables : undefined,
      status: state.status,
      taskId: isCheckRemoteRefsResult(state.data) ? state.data : null,
    }),
  });
  const latest = checks
    .filter(
      ({ variables }) =>
        variables?.repositoryId === repositoryId && variables.branchName === currentBranch.name
    )
    .at(-1);
  const taskId = latest?.status === "success" ? latest.taskId : null;
  const queryKey = repositoriesQueryKeys.remoteCheckTask({ taskId: taskId ?? "" });

  const { data } = useQuery({
    queryKey,
    queryFn: taskId
      ? async () => {
          const result = await getRemoteCheckTask({ taskId });
          // Not awaited, so the button is available again without waiting for a worker to answer.
          if (
            !result.isOngoing &&
            queryClient.getQueryData<GetRemoteCheckTaskResult>(queryKey)?.isOngoing !== false
          ) {
            queryClient.invalidateQueries({
              queryKey: repositoriesQueryKeys.repository({
                repositoryId,
                branchName: currentBranch.name,
              }),
            });
          }
          return result;
        }
      : skipToken,
    refetchInterval: (query) =>
      query.state.data?.isOngoing === false ? false : REMOTE_CHECK_TASK_POLL_INTERVAL_MS,
  });

  return {
    isSubmitting: latest?.status === "pending",
    // A failed poll keeps the last answer, and no answer yet counts as ongoing.
    isOngoing: taskId !== null && data?.isOngoing !== false,
    taskId,
  };
}
