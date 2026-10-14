import type { RepositoryActiveRun } from "@/entities/repository/domain/model/repository-activity";
import { LiveMarker } from "@/entities/repository/ui/repository-activity-card/activity-markers";
import {
  ActivityTime,
  WorkerId,
} from "@/entities/repository/ui/repository-activity-card/activity-values";
import { ElapsedTime } from "@/entities/repository/ui/repository-activity-card/elapsed-time";
import {
  getOperationLabel,
  getRunProgressText,
} from "@/entities/repository/ui/repository-activity-card/repository-activity.view";

export function ActiveRunRow({ run }: { run: RepositoryActiveRun }) {
  const progress = getRunProgressText(run);

  return (
    <li className="flex min-w-0 items-center gap-2.5 px-3 py-2">
      <LiveMarker />
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="flex min-w-0 items-baseline gap-2 text-sm">
          <span className="shrink-0 font-medium">{getOperationLabel(run.operation)}</span>
          {progress && <span className="min-w-0 truncate text-foreground-muted">{progress}</span>}
        </span>
        <span className="min-w-0 text-foreground-muted text-xs">
          Started <ActivityTime date={run.startedAt} /> on worker <WorkerId id={run.workerId} />
        </span>
      </div>
      <ElapsedTime since={run.startedAt} />
    </li>
  );
}
