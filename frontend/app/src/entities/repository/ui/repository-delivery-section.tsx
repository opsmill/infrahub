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
import type { AbandonmentRecord } from "@/entities/repository/domain/model/delivery-state";
import { PendingMergeList } from "@/entities/repository/ui/pending-merge-list";
import { useGetDeliveryState } from "@/entities/repository/ui/queries/get-delivery-state.query";
import { useImportCurrentCommitMutation } from "@/entities/repository/ui/queries/import-current-commit.mutation";
import {
  DELIVERY_TEXTS,
  REQUIRED_ACTION_BY_CAUSE,
} from "@/entities/repository/ui/repository-delivery-texts";
import { toastTaskStarted } from "@/entities/repository/ui/toast-task-started";

interface RepositoryDeliverySectionProps {
  repositoryId: string;
  permission: Permission;
}

export function RepositoryDeliverySection({
  repositoryId,
  permission,
}: RepositoryDeliverySectionProps) {
  return (
    <Card>
      <CardHeader>{DELIVERY_TEXTS.title}</CardHeader>
      <RepositoryDeliveryState repositoryId={repositoryId} permission={permission} />
    </Card>
  );
}

function RepositoryDeliveryState({ repositoryId, permission }: RepositoryDeliverySectionProps) {
  const { data: state, isPending, error } = useGetDeliveryState({ repositoryId });

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
        <p className="px-3 py-2 text-foreground-muted text-sm">{DELIVERY_TEXTS.nothingPending}</p>
        {lastAbandonment}
      </div>
    );
  }

  return (
    <div className="divide-y">
      <DetailRow label={DELIVERY_TEXTS.status}>
        <div>
          <ColorDisplay value={state.statusLabel} color={state.statusColor} />
        </div>
      </DetailRow>

      {state.cause && <DetailRow label={DELIVERY_TEXTS.cause}>{state.causeLabel}</DetailRow>}

      <DetailRow label={DELIVERY_TEXTS.requiredAction}>
        {state.cause && <p>{REQUIRED_ACTION_BY_CAUSE[state.cause]}</p>}
        <p>{DELIVERY_TEXTS.importsPaused}</p>
      </DetailRow>

      {state.error && (
        <DetailRow label={DELIVERY_TEXTS.remoteMessage}>
          <pre className="whitespace-pre-wrap break-words font-mono text-xs">{state.error}</pre>
        </DetailRow>
      )}

      {state.pendingMerges.length > 0 && (
        <DetailRow label={DELIVERY_TEXTS.pendingMerges}>
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
      toastTaskStarted(DELIVERY_TEXTS.reimportStarted, result.taskId);
      await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });

  return (
    <>
      <DetailRow label={DELIVERY_TEXTS.lastAbandonment}>
        <DateDisplay date={record.abandoned_at} />
      </DetailRow>

      <DetailRow label={DELIVERY_TEXTS.abandonedBy}>{record.account_name}</DetailRow>

      <DetailRow label={DELIVERY_TEXTS.abandonedMerges}>
        <PendingMergeList merges={record.entries} />
      </DetailRow>

      <DetailRow label={DELIVERY_TEXTS.recordedCommit}>
        <code className="text-xs">{record.recorded_commit.slice(0, 7)}</code>
      </DetailRow>

      <DetailRow label={DELIVERY_TEXTS.repositoryObjects}>
        <p>{DELIVERY_TEXTS.objectsCanStay}</p>
        {record.import_owed_commit && <p>{DELIVERY_TEXTS.objectsCanLack}</p>}
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
            {DELIVERY_TEXTS.reimport}
          </Button>
        </div>
      </DetailRow>
    </>
  );
}
