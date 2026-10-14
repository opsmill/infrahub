import { LockIcon } from "lucide-react";

import { Row } from "@/shared/components/container";

import type { RepositoryLock } from "@/entities/repository/domain/model/repository-activity";
import { IconMarker } from "@/entities/repository/ui/repository-activity-card/activity-markers";
import {
  ActivityTime,
  WorkerId,
} from "@/entities/repository/ui/repository-activity-card/activity-values";

interface LockLineProps {
  lock: RepositoryLock;
  /** The lock names only a worker, which can run several flows at once, so no run is named as holder. */
  isWorkerRunning: boolean;
}

export function LockLine({ lock, isWorkerRunning }: LockLineProps) {
  return (
    <Row className="min-w-0 gap-2.5 px-3 pt-1 pb-2">
      <IconMarker>
        <LockIcon className="size-3.5 shrink-0" />
      </IconMarker>
      <span className="min-w-0 text-foreground-muted text-xs">
        Repository lock held by worker <WorkerId id={lock.workerId} />
        {lock.requestedAt && (
          <>
            , requested <ActivityTime date={lock.requestedAt} />
          </>
        )}
        {!isWorkerRunning && ", with no active run"}
      </span>
    </Row>
  );
}
