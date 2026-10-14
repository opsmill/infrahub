import { Row } from "@/shared/components/container";

import type { RepositoryLastRun } from "@/entities/repository/domain/model/repository-activity";
import { DotMarker } from "@/entities/repository/ui/repository-activity-card/activity-markers";
import { ActivityTime } from "@/entities/repository/ui/repository-activity-card/activity-values";
import { getOperationLabel } from "@/entities/repository/ui/repository-activity-card/repository-activity.view";

export function IdleRow({ latestRun }: { latestRun: RepositoryLastRun | undefined }) {
  return (
    <Row className="min-w-0 gap-2.5 px-3 py-2">
      <DotMarker tone="neutral" />
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="text-sm">No activity</span>
        <span className="min-w-0 text-foreground-muted text-xs">
          {latestRun ? (
            <>
              Idle since the {getOperationLabel(latestRun.operation).toLowerCase()} finished{" "}
              <ActivityTime date={latestRun.finishedAt} />
            </>
          ) : (
            "No run in the last 30 days"
          )}
        </span>
      </div>
    </Row>
  );
}
