import { Card, CardHeader } from "@infrahub/ui";

import { ColorDisplay } from "@/shared/components/display/color-display";
import { DetailRow } from "@/shared/components/display/detail-row";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { PendingMergeList } from "@/entities/repository/ui/pending-merge-list";
import { useGetDeliveryState } from "@/entities/repository/ui/queries/get-delivery-state.query";
import {
  DELIVERY_TEXTS,
  REQUIRED_ACTION_BY_CAUSE,
} from "@/entities/repository/ui/repository-delivery-texts";

interface RepositoryDeliverySectionProps {
  repositoryId: string;
}

export function RepositoryDeliverySection({ repositoryId }: RepositoryDeliverySectionProps) {
  return (
    <Card>
      <CardHeader>{DELIVERY_TEXTS.title}</CardHeader>
      <RepositoryDeliveryState repositoryId={repositoryId} />
    </Card>
  );
}

function RepositoryDeliveryState({ repositoryId }: RepositoryDeliverySectionProps) {
  const { data: state, isPending, error } = useGetDeliveryState({ repositoryId });

  if (isPending) {
    return <LoadingIndicator className="p-3" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (state.status === "none") {
    return (
      <p className="px-3 py-2 text-foreground-muted text-sm">{DELIVERY_TEXTS.nothingPending}</p>
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
    </div>
  );
}
