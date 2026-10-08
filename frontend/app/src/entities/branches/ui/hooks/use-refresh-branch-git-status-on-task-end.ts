import { useQuery, useQueryClient } from "@tanstack/react-query";
import React from "react";

import { branchGitStatusQueryKeys } from "@/entities/branch-git-status/ui/queries/branch-git-status.query-keys";
import { isTaskFinishedQueryOptions } from "@/entities/tasks/ui/queries/is-task-finished.query";

// invalidation-at-callsite: the end of a background task, not a mutation, makes the Git status stale.
export function useRefreshBranchGitStatusOnTaskEnd(taskId: string | null) {
  const queryClient = useQueryClient();
  const { data: isFinished } = useQuery(isTaskFinishedQueryOptions({ taskId }));

  React.useEffect(() => {
    if (!isFinished) return;
    queryClient.invalidateQueries({ queryKey: branchGitStatusQueryKeys.all });
  }, [isFinished, queryClient]);
}

type GitStatusRefreshNavigationState = { gitStatusRefreshTaskId: string };

export function buildGitStatusRefreshNavigationState(
  taskId: string
): GitStatusRefreshNavigationState {
  return { gitStatusRefreshTaskId: taskId };
}

export function getGitStatusRefreshTaskId(state: unknown): string | null {
  if (typeof state !== "object" || state === null || !("gitStatusRefreshTaskId" in state)) {
    return null;
  }
  const { gitStatusRefreshTaskId } = state;
  return typeof gitStatusRefreshTaskId === "string" ? gitStatusRefreshTaskId : null;
}
