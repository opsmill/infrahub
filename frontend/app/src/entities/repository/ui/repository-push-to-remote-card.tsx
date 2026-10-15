import { Card, CardHeader } from "@infrahub/ui";

import { Col, Row } from "@/shared/components/container";
import { ColorDisplay } from "@/shared/components/display/color-display";
import { DateDisplay } from "@/shared/components/display/date-display";
import { DetailRow } from "@/shared/components/display/detail-row";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import type { PushFailureCause } from "@/entities/repository/domain/model/repository-push-state";
import { useGetRepositoryPushState } from "@/entities/repository/ui/queries/get-repository-push-state.query";

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
}

export function RepositoryPushToRemoteCard({ repositoryId }: RepositoryPushToRemoteCardProps) {
  return (
    <Card>
      <CardHeader>Push to remote</CardHeader>
      <RepositoryPushToRemoteState repositoryId={repositoryId} />
    </Card>
  );
}

function RepositoryPushToRemoteState({ repositoryId }: RepositoryPushToRemoteCardProps) {
  const { data: state, isPending, error } = useGetRepositoryPushState({ repositoryId });

  if (isPending) {
    return <LoadingIndicator className="p-3" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (state.status === "none") {
    return <p className="px-3 py-2 text-foreground-muted text-sm">Nothing pending</p>;
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
          <Col className="w-0 min-w-full gap-1">
            {state.pendingMerges.map((merge) => (
              <Row key={merge.entry_id}>
                <span className="min-w-0 truncate font-medium" title={merge.source_branch}>
                  {merge.source_branch}
                </span>
                <code className="text-xs">{merge.source_commit.slice(0, 7)}</code>
                <DateDisplay date={merge.merged_at} />
              </Row>
            ))}
          </Col>
        </DetailRow>
      )}
    </div>
  );
}
