import { TriangleAlertIcon } from "lucide-react";
import type React from "react";

import { RefreshButton } from "@/shared/components/buttons/refresh-button";
import { Col, Row } from "@/shared/components/container";
import { DateDisplay } from "@/shared/components/display/date-display";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { RepositoryCommitLog } from "@/entities/repository/domain/model/repository";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import {
  RepositoryCheckRemoteButton,
  type RepositoryRemoteCheck,
} from "@/entities/repository/ui/repository-check-remote-button";
import {
  getConditionNotice,
  getFreshness,
  getRebaseNote,
} from "@/entities/repository/ui/repository-commits.view";

interface RepositoryCommitsLogProps {
  log: RepositoryCommitLog;
}

export interface RepositoryCommitsRefreshButtonProps {
  repositoryId: string;
}

export interface RepositoryCommitsToolbarProps {
  repositoryId: string;
  /** Null where the repository has no remote check: a read-write repository. */
  remoteCheck: RepositoryRemoteCheck | null;
  children?: React.ReactNode;
}

export interface RepositoryCommitsHeaderProps
  extends RepositoryCommitsLogProps,
    Omit<RepositoryCommitsToolbarProps, "children"> {
  updatedOnlyByRebase: boolean;
}

export function RepositoryCommitsHeader({
  log,
  repositoryId,
  remoteCheck,
  updatedOnlyByRebase,
}: RepositoryCommitsHeaderProps) {
  const rebaseNote = updatedOnlyByRebase ? getRebaseNote(log) : null;

  return (
    <Col className="gap-1.5 p-2">
      <RepositoryCommitsToolbar repositoryId={repositoryId} remoteCheck={remoteCheck}>
        <FreshnessLine log={log} />
      </RepositoryCommitsToolbar>
      {rebaseNote && <p className="text-foreground-muted text-sm">{rebaseNote}</p>}
      <ConditionNotice log={log} updatedOnlyByRebase={updatedOnlyByRebase} />
    </Col>
  );
}

export function RepositoryCommitsToolbar({
  repositoryId,
  remoteCheck,
  children,
}: RepositoryCommitsToolbarProps) {
  return (
    <Row className="items-center gap-2">
      <RepositoryCommitsRefreshButton repositoryId={repositoryId} />
      {children}
      {remoteCheck && (
        <Row className="ml-auto">
          <RepositoryCheckRemoteButton repositoryId={repositoryId} {...remoteCheck} />
        </Row>
      )}
    </Row>
  );
}

function RepositoryCommitsRefreshButton({ repositoryId }: RepositoryCommitsRefreshButtonProps) {
  const { currentBranch } = useCurrentBranch();

  return (
    <RefreshButton
      className="rounded-md border-border-strong"
      queryKeys={[
        repositoriesQueryKeys.repository({
          repositoryId,
          branchName: currentBranch.name,
        }),
      ]}
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

function ConditionNotice({
  log,
  updatedOnlyByRebase,
}: RepositoryCommitsLogProps & Pick<RepositoryCommitsHeaderProps, "updatedOnlyByRebase">) {
  const notice = getConditionNotice(log, { updatedOnlyByRebase });

  if (!notice) return null;

  if (notice.tone === "neutral") {
    return <p className="font-medium text-sm">{notice.message}</p>;
  }

  return (
    <Row
      role="note"
      className="rounded-md border border-warning-border bg-warning-surface px-3 py-2 text-sm text-warning"
    >
      <TriangleAlertIcon className="size-4 shrink-0" aria-hidden="true" />
      <p>{notice.message}</p>
    </Row>
  );
}
