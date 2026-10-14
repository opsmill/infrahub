import { LockIcon } from "lucide-react";

import { Row } from "@/shared/components/container";

import type {
  RepositoryActiveRun,
  RepositoryLock,
} from "@/entities/repository/domain/model/repository-activity";
import { IconMarker } from "@/entities/repository/ui/repository-activity-card/activity-markers";
import {
  ActivityTime,
  WorkerId,
} from "@/entities/repository/ui/repository-activity-card/activity-values";
import { getOperationLabel } from "@/entities/repository/ui/repository-activity-card/repository-activity.view";

interface LockLineProps {
  lock: RepositoryLock;
  /** The active run whose worker holds the lock, if any. */
  holder: RepositoryActiveRun | undefined;
}

export function LockLine({ lock, holder }: LockLineProps) {
  return (
    <Row className="min-w-0 gap-2.5 px-3 pt-1 pb-2">
      <IconMarker>
        <LockIcon className="size-3.5 shrink-0" />
      </IconMarker>
      <span className="min-w-0 text-foreground-muted text-xs">
        Repository lock held by worker <WorkerId id={lock.workerId} />
        {holder && ` for the ${getOperationLabel(holder.operation).toLowerCase()}`}
        {lock.requestedAt && (
          <>
            , requested <ActivityTime date={lock.requestedAt} />
          </>
        )}
        {!holder && ", with no active run"}
      </span>
    </Row>
  );
}
