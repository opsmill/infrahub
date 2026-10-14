import { LockIcon } from "lucide-react";

import type {
  RepositoryActiveRun,
  RepositoryLock,
} from "@/entities/repository/domain/model/repository-activity";
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

interface ActiveRunRowProps {
  run: RepositoryActiveRun;
  /** The repository lock, when this run's worker holds it. */
  heldLock: RepositoryLock | null;
}

export function ActiveRunRow({ run, heldLock }: ActiveRunRowProps) {
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
          {heldLock && (
            <>
              <span aria-hidden className="px-1.5 text-foreground-muted/60">
                ·
              </span>
              <span className="whitespace-nowrap">
                <LockIcon aria-hidden className="mr-1 inline size-3 align-text-bottom" />
                Holds the repository lock
                {heldLock.requestedAt && (
                  <>
                    {" "}
                    (requested <ActivityTime date={heldLock.requestedAt} />)
                  </>
                )}
              </span>
            </>
          )}
        </span>
      </div>
      <ElapsedTime since={run.startedAt} />
    </li>
  );
}
