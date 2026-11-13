import { Card, CardHeader } from "@infrahub/ui";
import type React from "react";
import { ErrorBoundary } from "react-error-boundary";

import { Row } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/loading/skeleton";

import type { RepositoryActivity } from "@/entities/repository/domain/model/repository-activity";
import { useGetRepositoryActivity } from "@/entities/repository/ui/queries/get-repository-activity.query";
import { ActiveRunRow } from "@/entities/repository/ui/repository-activity-card/active-run-row";
import { IdleRow } from "@/entities/repository/ui/repository-activity-card/idle-row";
import { RepositoryLastRuns } from "@/entities/repository/ui/repository-activity-card/repository-last-runs";
import { RepositoryLockRow } from "@/entities/repository/ui/repository-activity-card/repository-lock-row";

export const ACTIVITY_LOAD_FAILED =
  "Could not load the repository activity. Reload the page to try again.";

function Message({ children }: { children: React.ReactNode }) {
  return <div className="px-3 py-6 text-center text-foreground-muted text-sm">{children}</div>;
}

function ActivitySkeleton() {
  return (
    <>
      <Row className="my-1 gap-2.5 px-3 py-3">
        <Skeleton className="size-2 rounded-full" />
        <div className="flex flex-col gap-1">
          <Skeleton className="h-3.5 w-24" />
          <Skeleton className="h-3 w-64" />
        </div>
      </Row>
      <Row className="h-10 gap-2.5 border-t px-3">
        <Skeleton className="size-2 rounded-full" />
        <Skeleton className="h-3 w-56" />
      </Row>
    </>
  );
}

function RepositoryActiveRuns({ activity }: { activity: RepositoryActivity }) {
  const { activeRuns, lastRuns, lock } = activity;

  return (
    <div className="py-1">
      {activeRuns.length === 0 ? (
        <IdleRow latestRun={lastRuns[0]} />
      ) : (
        <ul>
          {activeRuns.map((run) => (
            <ActiveRunRow key={run.runId} run={run} />
          ))}
        </ul>
      )}

      {lock && (
        <RepositoryLockRow
          lock={lock}
          isWorkerRunning={activeRuns.some(({ workerId }) => workerId === lock.workerId)}
        />
      )}
    </div>
  );
}

function RepositoryActivityBody({ repositoryId }: { repositoryId: string }) {
  const { data, error, isPending } = useGetRepositoryActivity({ repositoryId });

  if (isPending) {
    return <ActivitySkeleton />;
  }

  if (error) {
    return <Message>{ACTIVITY_LOAD_FAILED}</Message>;
  }

  return (
    <>
      <RepositoryActiveRuns activity={data} />
      <RepositoryLastRuns runs={data.lastRuns} />
    </>
  );
}

export function RepositoryActivityCard({ repositoryId }: { repositoryId: string }) {
  return (
    <Card className="overflow-hidden">
      <CardHeader>Repository activity</CardHeader>

      <ErrorBoundary fallbackRender={() => <Message>{ACTIVITY_LOAD_FAILED}</Message>}>
        <RepositoryActivityBody repositoryId={repositoryId} />
      </ErrorBoundary>
    </Card>
  );
}
