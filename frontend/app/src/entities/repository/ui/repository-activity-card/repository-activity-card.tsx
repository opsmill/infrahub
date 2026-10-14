import { Card, CardHeader } from "@infrahub/ui";
import React from "react";
import { ErrorBoundary } from "react-error-boundary";

import { Row } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/loading/skeleton";

import type { RepositoryActivity } from "@/entities/repository/domain/model/repository-activity";
import { isRepositoryActivityAccessDenied } from "@/entities/repository/domain/rules/repository-activity-error";
import { useGetRepositoryActivity } from "@/entities/repository/ui/queries/get-repository-activity.query";
import { ActiveRunRow } from "@/entities/repository/ui/repository-activity-card/active-run-row";
import { IdleRow } from "@/entities/repository/ui/repository-activity-card/idle-row";
import { LastRuns } from "@/entities/repository/ui/repository-activity-card/last-runs";
import { LockLine } from "@/entities/repository/ui/repository-activity-card/lock-line";

export const ACTIVITY_CHECK_FAILED = "The activity of this repository could not be checked.";
export const ACTIVITY_PERMISSION_DENIED =
  "You do not have permission to view the activity of this repository.";

function Message({ children }: { children: React.ReactNode }) {
  return (
    <div role="status" className="px-3 py-6 text-center text-foreground-muted text-sm">
      {children}
    </div>
  );
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

function CurrentActivity({ activity }: { activity: RepositoryActivity }) {
  const { activeRuns, lastRuns, lock } = activity;
  const holder = lock ? activeRuns.find(({ workerId }) => workerId === lock.workerId) : undefined;

  return (
    <section aria-label="Current activity" className="py-1">
      <div role="status">
        {activeRuns.length === 0 ? (
          <IdleRow latestRun={lastRuns[0]} />
        ) : (
          <ul>
            {activeRuns.map((run) => (
              <ActiveRunRow
                key={run.runId}
                run={run}
                heldLock={run.runId === holder?.runId ? lock : null}
              />
            ))}
          </ul>
        )}
      </div>
      {lock && <LockLine lock={lock} holder={holder} />}
    </section>
  );
}

interface RepositoryActivityBodyProps {
  data: RepositoryActivity | undefined;
  error: Error | null;
  isPending: boolean;
}

function RepositoryActivityBody({ data, error, isPending }: RepositoryActivityBodyProps) {
  if (isPending) return <ActivitySkeleton />;

  if (isRepositoryActivityAccessDenied(error)) {
    return <Message>{ACTIVITY_PERMISSION_DENIED}</Message>;
  }

  // A failed check drops the running state it can no longer vouch for; finished runs stay true.
  if (error || !data) {
    return (
      <>
        <Message>{ACTIVITY_CHECK_FAILED}</Message>
        {data && <LastRuns runs={data.lastRuns} />}
      </>
    );
  }

  return (
    <>
      <CurrentActivity activity={data} />
      <LastRuns runs={data.lastRuns} />
    </>
  );
}

export function RepositoryActivityCard({ repositoryId }: { repositoryId: string }) {
  const titleId = React.useId();
  const { data, error, isPending } = useGetRepositoryActivity({ repositoryId });

  return (
    <Card role="region" aria-labelledby={titleId} className="overflow-hidden">
      <CardHeader>
        <h2 id={titleId}>Repository activity</h2>
      </CardHeader>

      <ErrorBoundary
        fallbackRender={() => <Message>{ACTIVITY_CHECK_FAILED}</Message>}
        resetKeys={[data]}
      >
        <RepositoryActivityBody data={data} error={error} isPending={isPending} />
      </ErrorBoundary>
    </Card>
  );
}
