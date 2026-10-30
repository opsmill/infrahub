import { useQuery, useQueryClient } from "@tanstack/react-query";
import React from "react";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useRefreshBranchGitStatusOnTaskEnd } from "@/entities/branches/ui/hooks/use-refresh-branch-git-status-on-task-end";
import { getBranchActionStateQueryOptions } from "@/entities/branches/ui/queries/get-branch-action-state.query";
import { useRebaseBranch } from "@/entities/branches/ui/queries/rebase-branch.mutation";
import {
  EDIT_DEFAULT_BRANCH,
  type PermissionDecision,
  REBASE_BRANCH,
} from "@/entities/permission/domain/model/permission";
import { hasGlobalPermissionQueryOptions } from "@/entities/permission/ui/queries/has-global-permission.query";
import { useCheckRemoteRefsMutation } from "@/entities/repository/ui/queries/check-remote-refs.mutation";
import { useGetRemoteCheckTask } from "@/entities/repository/ui/queries/get-remote-check-task.query";
import { getLatestRepositoryImportTaskQueryOptions } from "@/entities/repository/ui/queries/get-repository-import-error.query";
import { useReimportLastCommitMutation } from "@/entities/repository/ui/queries/reimport-last-commit.mutation";
import {
  repositoriesQueryKeys,
  repositoryQueryKeys,
} from "@/entities/repository/ui/queries/repository.query-keys";
import {
  type ActionAccess,
  type CommitLogActionKind,
  type CommitLogStatusContext,
  getRebaseAccess,
  getRepositoryActionAccess,
  isErrorNotToastedByClient,
} from "@/entities/repository/ui/repository-commits.view";
import { BRANCH_REBASE_WORKFLOW, TASK_ONGOING_STATES } from "@/entities/tasks/domain/model/task";
import { isTaskFinishedQueryOptions } from "@/entities/tasks/ui/queries/is-task-finished.query";
import { toastTaskStarted } from "@/entities/tasks/ui/toast-task-started";

export interface RepositoryCommitsActions {
  running: CommitLogStatusContext["running"];
  repositoryAccess: ActionAccess;
  rebaseAccess: ActionAccess;
  submitting: CommitLogActionKind | null;
  isCheckRunning: boolean;
  importLatestCommit: () => void;
  rebaseBranch: (options: { onSettled: () => void }) => void;
  checkRemote: () => void;
}

export interface UseRepositoryCommitsActionsParams {
  repositoryId: string;
  isReadOnly: boolean;
  rebaseOnly: boolean;
  updatePermission: PermissionDecision;
}

export function useRepositoryCommitsActions({
  repositoryId,
  isReadOnly,
  rebaseOnly,
  updatePermission,
}: UseRepositoryCommitsActionsParams): RepositoryCommitsActions {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();
  const { isAuthenticated, user } = useAuth();
  const branchName = currentBranch.name;
  const isDefaultBranch = !!currentBranch.is_default;

  const editDefaultBranch = useQuery({
    ...hasGlobalPermissionQueryOptions(EDIT_DEFAULT_BRANCH, user?.id),
    enabled: isDefaultBranch && isAuthenticated,
  });
  const rebasePermission = useQuery({
    ...hasGlobalPermissionQueryOptions(REBASE_BRANCH, user?.id),
    enabled: rebaseOnly && isAuthenticated,
  });

  const latestImportTaskKey = repositoryQueryKeys.latestImportTask({ branchName, repositoryId });
  const { data: latestImport } = useQuery({
    ...getLatestRepositoryImportTaskQueryOptions({ branchName, repositoryId, isSyncing: false }),
    enabled: isReadOnly,
  });
  const importMutation = useReimportLastCommitMutation({
    onSuccess: async (result) => {
      toastTaskStarted("Import of the latest commit started.", result.taskId);
      await queryClient.invalidateQueries({ queryKey: latestImportTaskKey });
    },
  });
  const isStartedImportRunning = useIsTaskRunning(importMutation.data?.taskId ?? null);

  const rebaseMutation = useRebaseBranch();
  const startedRebaseTaskId = rebaseMutation.data?.relatedTaskId ?? null;
  const isStartedRebaseRunning = useIsTaskRunning(startedRebaseTaskId);
  useRefreshBranchGitStatusOnTaskEnd(startedRebaseTaskId);
  const ongoingRebases = useQuery({
    ...getBranchActionStateQueryOptions({
      branchName,
      workflow: [BRANCH_REBASE_WORKFLOW],
      state: TASK_ONGOING_STATES,
    }),
    enabled: rebaseOnly,
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  });
  const isRebaseRunning =
    isStartedRebaseRunning || (rebaseOnly && (ongoingRebases.data?.ongoingTaskCount ?? 0) > 0);

  const { mutate: checkRemoteRefs } = useCheckRemoteRefsMutation();
  const remoteCheck = useGetRemoteCheckTask({ repositoryId });

  const running = isRebaseRunning
    ? "rebase"
    : (isReadOnly && latestImport?.status === "running") || isStartedImportRunning
      ? "import"
      : null;

  useRefreshCommitLogWhenTaskEnds({ isRunning: running !== null, repositoryId, branchName });

  // A failed lookup leaves the decision to the server, which checks the permission again.
  const canEditDefaultBranch = editDefaultBranch.isError ? true : editDefaultBranch.data;
  const canRebase = rebasePermission.isError ? true : rebasePermission.data;

  return {
    running,
    repositoryAccess: getRepositoryActionAccess({
      isAuthenticated,
      branchStatus: currentBranch.status,
      updatePermission,
      isDefaultBranch,
      canEditDefaultBranch,
    }),
    rebaseAccess: getRebaseAccess({
      isAuthenticated,
      isDefaultBranch,
      branchStatus: currentBranch.status,
      canRebase,
      isRunningKnown: !ongoingRebases.isPending,
    }),
    submitting: importMutation.isPending
      ? "import"
      : rebaseMutation.isPending
        ? "rebase"
        : remoteCheck.isSubmitting
          ? "check"
          : null,
    isCheckRunning: remoteCheck.isOngoing,
    importLatestCommit: () =>
      importMutation.mutate(
        { repositoryId },
        { onError: (error) => toastIfClientShowedNone("importing the latest commit", error) }
      ),
    rebaseBranch: ({ onSettled }) =>
      rebaseMutation.mutate(
        { branchName, waitUntilCompletion: false },
        {
          onSuccess: (result) =>
            toastTaskStarted("Branch rebase started.", result.relatedTaskId ?? undefined),
          onError: (error) => toastIfClientShowedNone("rebasing the branch", error),
          onSettled,
        }
      ),
    checkRemote: () =>
      checkRemoteRefs(
        { repositoryId, branchName },
        {
          onError: (error) => {
            toast(
              <Alert
                type={ALERT_TYPES.ERROR}
                message={`Error checking the remote: ${error.message}`}
              />
            );
          },
        }
      ),
  };
}

function toastIfClientShowedNone(doing: string, error: Error) {
  if (!isErrorNotToastedByClient(error)) return;
  toast(<Alert type={ALERT_TYPES.ERROR} message={`Error ${doing}: ${error.message}`} />);
}

// The poll sets an infinite stale time once the task ends or the poll gives up, so only a stale result can still be running.
function useIsTaskRunning(taskId: string | null): boolean {
  const { data: isFinished, isStale } = useQuery(isTaskFinishedQueryOptions({ taskId }));
  return taskId !== null && !isFinished && isStale;
}

// invalidation-at-callsite: the end of a background task, not a mutation, makes the commit log stale.
function useRefreshCommitLogWhenTaskEnds({
  isRunning,
  repositoryId,
  branchName,
}: {
  isRunning: boolean;
  repositoryId: string;
  branchName: string;
}) {
  const queryClient = useQueryClient();
  const wasRunning = React.useRef(isRunning);

  React.useEffect(() => {
    if (wasRunning.current && !isRunning) {
      queryClient.invalidateQueries({
        queryKey: repositoriesQueryKeys.repository({ repositoryId, branchName }),
      });
    }
    wasRunning.current = isRunning;
  }, [isRunning, queryClient, repositoryId, branchName]);
}
