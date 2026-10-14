import { LockIcon } from "lucide-react";

import { Row } from "@/shared/components/container";
import { DateDisplay } from "@/shared/components/display/date-display";

import type { RepositoryLock } from "@/entities/repository/domain/model/repository-activity";
import { IconMarker } from "@/entities/repository/ui/repository-activity-card/activity-markers";

interface RepositoryLockRowProps {
  lock: RepositoryLock;
  isWorkerRunning: boolean;
}

export function RepositoryLockRow({ lock, isWorkerRunning }: RepositoryLockRowProps) {
  return (
    <Row className="min-w-0 gap-2.5 px-3 pt-1 pb-2">
      <IconMarker>
        <LockIcon className="size-3.5 shrink-0" />
      </IconMarker>
      <span className="min-w-0 text-foreground-muted text-xs">
        Repository lock held by worker {lock.workerId}
        {lock.requestedAt && (
          <>
            , requested{" "}
            <DateDisplay
              date={lock.requestedAt}
              fullTimestamp
              containerClassName="inline-flex shrink-0"
            />
          </>
        )}
        {!isWorkerRunning && ", with no active run"}
      </span>
    </Row>
  );
}
