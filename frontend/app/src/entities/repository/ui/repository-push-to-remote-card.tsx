import { Button, Card, CardHeader } from "@infrahub/ui";

import { queryClient } from "@/shared/api/rest/client";
import { ColorDisplay } from "@/shared/components/display/color-display";
import { DateDisplay } from "@/shared/components/display/date-display";
import { DetailRow } from "@/shared/components/display/detail-row";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type {
  AbandonmentRecord,
  PushFailureCause,
} from "@/entities/repository/domain/model/repository-push-state";
import { PendingMergeList } from "@/entities/repository/ui/pending-merge-list";
import { useGetRepositoryPushState } from "@/entities/repository/ui/queries/get-repository-push-state.query";
import { useImportCurrentCommitMutation } from "@/entities/repository/ui/queries/import-current-commit.mutation";
import { toastTaskStarted } from "@/entities/repository/ui/toast-task-started";

const REQUIRED_ACTION_BY_CAUSE: Record<PushFailureCause, string> = {
  "remote-unreachable": "Wait, or retry once the remote is reachable.",
  "remote-advanced": "Wait, or retry.",
  "record-failed": "Wait, or retry. The remote has the content.",
  "not-found": "Check the location, and that the credential can see the repository, then retry.",
  certificate: "Fix the certificate configuration, then retry.",
  credentials: "Fix the credential, then retry.",
  permission: "Grant push permission or lift the branch protection, then retry.",
  "import-interrupted":
    "Wait, or retry once the database and the remote are reachable. The remote has the content.",
  "import-failed": "Fix the content on the remote, then retry.",
  "replay-conflict": "Merge the source branch on the remote by hand, then retry. Or abandon.",
  "source-discarded": "Abandon.",
  "destination-rewritten": "Abandon.",
  unclassified: "Read the message, then retry or abandon.",
};

interface RepositoryPushToRemoteCardProps {
  repositoryId: string;
  permission: Permission;
}

export function RepositoryPushToRemoteCard({
  repositoryId,
  permission,
}: RepositoryPushToRemoteCardProps) {
  return (
    <Card>
      <CardHeader>Push to remote</CardHeader>
      <RepositoryPushToRemoteState repositoryId={repositoryId} permission={permission} />
    </Card>
  );
}

function RepositoryPushToRemoteState({
  repositoryId,
  permission,
}: RepositoryPushToRemoteCardProps) {
  const { data: state, isPending, error } = useGetRepositoryPushState({ repositoryId });

  if (isPending) {
    return <LoadingIndicator className="p-3" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const lastAbandonment = state.lastAbandonment && (
    <LastAbandonment
      repositoryId={repositoryId}
      record={state.lastAbandonment}
      isUpdateAllowed={permission.update.isAllowed}
    />
  );

  if (state.status === "none") {
    return (
      <div className="divide-y">
        <p className="px-3 py-2 text-foreground-muted text-sm">Nothing pending</p>
        {lastAbandonment}
      </div>
    );
  }

  const isActionRequired = state.status === "action-required";

  return (
    <div className="divide-y">
      <DetailRow label="Status">
        <div>
          <ColorDisplay value={state.statusLabel} color={state.statusColor} />
        </div>
        <p>Imports from the remote default branch are paused until the pending pushes clear.</p>
      </DetailRow>

      {isActionRequired && state.cause && (
        <>
          <DetailRow label="Cause">{state.causeLabel}</DetailRow>
          <DetailRow label="Required action">{REQUIRED_ACTION_BY_CAUSE[state.cause]}</DetailRow>
        </>
      )}

      {isActionRequired && state.error && (
        <DetailRow label="Message from the remote">
          <pre className="w-0 min-w-full overflow-x-auto text-xs">{state.error}</pre>
        </DetailRow>
      )}

      {state.pendingMerges.length > 0 && (
        <DetailRow label="Pending merges">
          <PendingMergeList merges={state.pendingMerges} />
        </DetailRow>
      )}

      {lastAbandonment}
    </div>
  );
}

interface LastAbandonmentProps {
  repositoryId: string;
  record: AbandonmentRecord;
  isUpdateAllowed: boolean;
}

function LastAbandonment({ repositoryId, record, isUpdateAllowed }: LastAbandonmentProps) {
  const defaultBranch = useDefaultBranch();

  // The client's own error toast shows the refusal message of the backend.
  const { mutate: importCurrentCommit, isPending } = useImportCurrentCommitMutation({
    onSuccess: async (result) => {
      toastTaskStarted("Import of current commit started.", result.taskId);
      await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });

  return (
    <>
      <DetailRow label="Last abandonment">
        <DateDisplay date={record.abandoned_at} />
      </DetailRow>

      <DetailRow label="Abandoned by">{record.account_name}</DetailRow>

      <DetailRow label="Abandoned merges">
        <PendingMergeList merges={record.entries} />
      </DetailRow>

      <DetailRow label="Recorded commit">
        <code className="text-xs">{record.recorded_commit.slice(0, 7)}</code>
      </DetailRow>

      <DetailRow label="Repository objects">
        <p>The default branch can hold repository objects that the recorded commit lacks.</p>
        {record.import_owed_commit && (
          <p>The default branch can also lack repository objects that the recorded commit holds.</p>
        )}
        <div>
          {/* The repository objects live on the default branch, whatever branch the user selected. */}
          <Button
            size="sm"
            variant="outline"
            isDisabled={!isUpdateAllowed || !defaultBranch}
            isPending={isPending}
            onPress={() =>
              defaultBranch && importCurrentCommit({ repositoryId, branchName: defaultBranch.name })
            }
          >
            Reimport current commit
          </Button>
        </div>
      </DetailRow>
    </>
  );
}
