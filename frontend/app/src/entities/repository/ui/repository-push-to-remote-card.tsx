import { Button, Card, CardHeader } from "@infrahub/ui";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ColorDisplay } from "@/shared/components/display/color-display";
import { DateDisplay } from "@/shared/components/display/date-display";
import { DetailRow } from "@/shared/components/display/detail-row";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type {
  AbandonedPush,
  PushFailureCause,
  RepositoryPushState,
} from "@/entities/repository/domain/model/repository-push-state";
import { usePendingPushPermissions } from "@/entities/repository/ui/hooks/use-pending-push-permissions";
import { PendingMergeList } from "@/entities/repository/ui/pending-merge-list";
import { useGetRepositoryPushState } from "@/entities/repository/ui/queries/get-repository-push-state.query";
import { useImportCurrentCommitMutation } from "@/entities/repository/ui/queries/import-current-commit.mutation";
import { toastTaskStarted } from "@/entities/tasks/ui/toast-task-started";

const REQUIRED_ACTION_BY_CAUSE: Record<PushFailureCause, string> = {
  "remote-unreachable": "Wait, or retry once the remote is reachable.",
  "remote-advanced": "Wait, or retry.",
  "record-failed": "Wait, or retry. The remote can already have the content.",
  "not-found": "Check the location, and that the credential can see the repository, then retry.",
  certificate: "Fix the certificate configuration, then retry.",
  credentials: "Fix the credential, then retry.",
  permission: "Grant push permission or lift the branch protection, then retry.",
  "import-interrupted":
    "Wait, or retry once the database, the Infrahub server and the remote are reachable. The remote already has the content.",
  "import-failed": "Fix the content on the remote, then retry.",
  "replay-conflict": "Merge the source branch on the remote by hand, then retry. Or abandon.",
  "source-discarded": "Abandon.",
  "destination-rewritten": "Abandon.",
  unclassified: "Read the message, then retry or abandon.",
};

interface RepositoryPushToRemoteCardProps {
  repositoryId: string;
}

export function RepositoryPushToRemoteCard({ repositoryId }: RepositoryPushToRemoteCardProps) {
  return (
    <Card>
      <CardHeader>Push to remote</CardHeader>
      <PushStateDetails repositoryId={repositoryId} />
    </Card>
  );
}

function PushStateDetails({ repositoryId }: RepositoryPushToRemoteCardProps) {
  const { data: pushState, isPending, error } = useGetRepositoryPushState({ repositoryId });

  if (isPending) {
    return <LoadingIndicator className="p-3" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return (
    <div className="divide-y">
      <PendingPushDetails pushState={pushState} />
      <AbandonedPushDetails
        repositoryId={repositoryId}
        abandonedPush={pushState.lastAbandonedPush}
        hasPendingPushes={pushState.status !== "none"}
      />
    </div>
  );
}

interface PendingPushDetailsProps {
  pushState: RepositoryPushState;
}

function PendingPushDetails({ pushState }: PendingPushDetailsProps) {
  if (pushState.status === "none") {
    return <p className="px-3 py-2 text-foreground-muted text-sm">Nothing pending</p>;
  }

  // While a retry runs, the cause and the message of the last failure no longer apply.
  const isActionRequired = pushState.status === "action-required";

  return (
    <>
      <DetailRow label="Status">
        <div>
          <ColorDisplay value={pushState.statusLabel} color={pushState.statusColor} />
        </div>
        <p>Imports from the remote default branch are paused until the pending pushes clear.</p>
      </DetailRow>

      {isActionRequired && pushState.cause && (
        <>
          <DetailRow label="Cause">{pushState.causeLabel}</DetailRow>
          <DetailRow label="Required action">{REQUIRED_ACTION_BY_CAUSE[pushState.cause]}</DetailRow>
        </>
      )}

      {isActionRequired && pushState.error && (
        <DetailRow label="Message from the remote">
          <pre className="w-0 min-w-full overflow-x-auto text-xs">{pushState.error}</pre>
        </DetailRow>
      )}

      {pushState.pendingMerges.length > 0 && (
        <DetailRow label="Pending merges">
          <PendingMergeList merges={pushState.pendingMerges} />
        </DetailRow>
      )}
    </>
  );
}

interface AbandonedPushDetailsProps {
  repositoryId: string;
  abandonedPush: AbandonedPush | null;
  hasPendingPushes: boolean;
}

function AbandonedPushDetails({
  repositoryId,
  abandonedPush,
  hasPendingPushes,
}: AbandonedPushDetailsProps) {
  if (!abandonedPush) {
    return null;
  }

  return (
    <>
      <DetailRow label="Last abandoned push">
        <DateDisplay date={abandonedPush.abandoned_at} />
      </DetailRow>

      <DetailRow label="Abandoned by">{abandonedPush.account_name}</DetailRow>

      <DetailRow label="Abandoned merges">
        <PendingMergeList merges={abandonedPush.entries} />
      </DetailRow>

      {/* The backend records an empty commit when it could not read the one the default branch kept. */}
      {abandonedPush.recorded_commit && (
        <DetailRow label="Recorded commit">
          <code className="text-xs">{abandonedPush.recorded_commit.slice(0, 7)}</code>
        </DetailRow>
      )}

      <DetailRow label="Repository objects">
        <p>The default branch can hold repository objects that the recorded commit lacks.</p>
        {abandonedPush.import_owed_commit && (
          <p>The default branch can also lack repository objects that the recorded commit holds.</p>
        )}
        {/* The backend refuses a reimport while pushes are pending. */}
        {!hasPendingPushes && <ReimportOnDefaultBranchButton repositoryId={repositoryId} />}
      </DetailRow>
    </>
  );
}

interface ReimportOnDefaultBranchButtonProps {
  repositoryId: string;
}

function ReimportOnDefaultBranchButton({ repositoryId }: ReimportOnDefaultBranchButtonProps) {
  const defaultBranch = useDefaultBranch();
  const { canReimportOnDefaultBranch } = usePendingPushPermissions();

  const { mutate: importCurrentCommit, isPending: isReimporting } = useImportCurrentCommitMutation({
    onSuccess: async (result) => {
      toastTaskStarted("Import of current commit started.", result.taskId);
      await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
    onError: (error) => {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={`Error importing current commit: ${error.message}`}
        />
      );
    },
  });

  if (!defaultBranch) {
    return null;
  }

  // Abandoning changed the default branch, so the reimport runs there whatever branch the user selected.
  return (
    <div>
      <Button
        size="sm"
        variant="outline"
        isDisabled={!canReimportOnDefaultBranch}
        isPending={isReimporting}
        onPress={() => importCurrentCommit({ repositoryId, branchName: defaultBranch.name })}
      >
        Reimport current commit
      </Button>
    </div>
  );
}
