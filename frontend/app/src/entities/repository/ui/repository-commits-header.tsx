import { TriangleAlertIcon } from "lucide-react";

import { Col, Row } from "@/shared/components/container";
import { DateDisplay } from "@/shared/components/display/date-display";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { RefreshButton } from "@/entities/nodes/object/ui/object-details/refresh-button";
import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import type { RepositoryCommitLog } from "@/entities/repository/domain/model/repository";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import { RepositoryCheckRemoteButton } from "@/entities/repository/ui/repository-check-remote-button";
import { getConditionNotice, getFreshness } from "@/entities/repository/ui/repository-commits.view";

interface RepositoryCommitsLogProps {
  log: RepositoryCommitLog;
}

export interface RepositoryCommitsRefreshButtonProps {
  repositoryId: string;
}

export interface RepositoryCommitsHeaderProps
  extends RepositoryCommitsLogProps,
    RepositoryCommitsRefreshButtonProps {
  isReadOnly: boolean;
  updatePermission: PermissionDecision;
}

export function RepositoryCommitsHeader({
  log,
  repositoryId,
  isReadOnly,
  updatePermission,
}: RepositoryCommitsHeaderProps) {
  return (
    <Col className="gap-1.5 p-2">
      <Row className="items-center gap-2">
        <RepositoryCommitsRefreshButton repositoryId={repositoryId} />
        <FreshnessLine log={log} />
        {isReadOnly && (
          <RepositoryCheckRemoteButton
            repositoryId={repositoryId}
            updatePermission={updatePermission}
          />
        )}
      </Row>
      <ConditionNotice log={log} />
    </Col>
  );
}

export function RepositoryCommitsRefreshButton({
  repositoryId,
}: RepositoryCommitsRefreshButtonProps) {
  const { currentBranch } = useCurrentBranch();

  return (
    <RefreshButton
      className="rounded-md border-border-strong"
      queryKey={repositoriesQueryKeys.repository({
        repositoryId,
        branchName: currentBranch.name,
      })}
    />
  );
}

function FreshnessLine({ log }: RepositoryCommitsLogProps) {
  const { trackedRef, checkedAt, updatedAt } = getFreshness(log);

  return (
    <p className="flex flex-wrap items-center gap-x-1.5 text-foreground-muted text-sm">
      {trackedRef && (
        <span className="flex items-center gap-1">
          Tracking <code className="font-mono text-foreground text-xs">{trackedRef}</code>
        </span>
      )}
      {checkedAt && (
        <span className="flex items-center gap-1">
          Checked <DateDisplay date={checkedAt} fullTimestamp className="text-sm" />
        </span>
      )}
      {updatedAt && (
        <span className="flex items-center gap-1">
          Updated <DateDisplay date={updatedAt} fullTimestamp className="text-sm" />
        </span>
      )}
    </p>
  );
}

function ConditionNotice({ log }: RepositoryCommitsLogProps) {
  const notice = getConditionNotice(log);

  if (!notice) return null;

  if (notice.tone === "neutral") {
    return <p className="font-medium text-sm">{notice.message}</p>;
  }

  return (
    <Row
      role="note"
      className="rounded-md bg-amber-50 px-3 py-2 text-amber-800 text-sm dark:bg-amber-200/10 dark:text-amber-200"
    >
      <TriangleAlertIcon className="size-4 shrink-0" aria-hidden="true" />
      <p>{notice.message}</p>
    </Row>
  );
}
