import { Card, CardHeader } from "@infrahub/ui";

import { ColorDisplay } from "@/shared/components/display/color-display";
import { DateDisplay } from "@/shared/components/display/date-display";
import { DetailRow } from "@/shared/components/display/detail-row";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

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
        <ColorDisplay value={state.statusLabel} color={state.statusColor} />
      </DetailRow>

      {state.cause && (
        <DetailRow label={DELIVERY_TEXTS.cause}>{state.causeLabel ?? state.cause}</DetailRow>
      )}

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
          <ol className="flex flex-col gap-1">
            {state.pendingMerges.map((merge) => (
              <li key={merge.entry_id} className="flex items-center gap-2">
                <span className="font-medium">{merge.source_branch}</span>
                <code className="text-xs">{merge.source_commit.slice(0, 7)}</code>
                <DateDisplay date={merge.merged_at} />
              </li>
            ))}
          </ol>
        </DetailRow>
      )}
    </div>
  );
}
