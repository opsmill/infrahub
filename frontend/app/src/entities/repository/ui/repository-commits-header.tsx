import { Spinner } from "@infrahub/ui";
import {
  ArrowDownToLineIcon,
  CircleCheckIcon,
  CircleDashedIcon,
  GitBranchIcon,
  type LucideIcon,
  TriangleAlertIcon,
} from "lucide-react";
import React from "react";

import { Col, Row } from "@/shared/components/container";
import { DateDisplay } from "@/shared/components/display/date-display";
import { classNames } from "@/shared/utils/common";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import type { RepositoryCommitLog } from "@/entities/repository/domain/model/repository";
import {
  type RepositoryCommitsActions,
  useRepositoryCommitsActions,
} from "@/entities/repository/ui/hooks/use-repository-commits-actions";
import {
  type CommitLogAction,
  type CommitLogHeaderState,
  type CommitLogStatus,
  type CommitLogStatusIcon,
  type CommitLogStatusTone,
  type CommitLogTextPart,
  getCheckAction,
  getCommitLogStatus,
  getFreshness,
  getUnavailableStatus,
  type RepositoryCommitsRepository,
} from "@/entities/repository/ui/repository-commits.view";
import {
  CommitLogActionButton,
  CommitLogRefreshButton,
  Ref,
  RepositoryCommitsStatusActions,
} from "@/entities/repository/ui/repository-commits-status-actions";

export interface RepositoryCommitsHeaderProps {
  commitLog: CommitLogHeaderState;
  repository: RepositoryCommitsRepository;
  rebaseOnly: boolean;
}

export function RepositoryCommitsHeader({
  commitLog,
  repository,
  rebaseOnly,
}: RepositoryCommitsHeaderProps) {
  const { currentBranch } = useCurrentBranch();
  const defaultBranchName = useDefaultBranch()?.name ?? null;
  const actions = useRepositoryCommitsActions({
    repositoryId: repository.id,
    isReadOnly: repository.isReadOnly,
    rebaseOnly,
    updatePermission: repository.updatePermission,
  });

  const checkAction = getCheckAction({
    isReadOnly: repository.isReadOnly,
    isActive: repository.isActive,
    repositoryAccess: actions.repositoryAccess,
  });

  switch (commitLog.kind) {
    case "loading":
      return <LoadingBlock />;
    case "failed":
      return <Toolbar repositoryId={repository.id} checkAction={checkAction} actions={actions} />;
  }

  const status =
    commitLog.kind === "unavailable"
      ? getUnavailableStatus(commitLog.emptyState, {
          isRetrying: commitLog.isRetrying,
          checkAction,
        })
      : getCommitLogStatus(commitLog.log, {
          isReadOnly: repository.isReadOnly,
          rebaseOnly,
          isStaging: repository.isStaging,
          isActive: repository.isActive,
          branchName: currentBranch.name,
          defaultBranchName,
          running: actions.running,
          repositoryAccess: actions.repositoryAccess,
          rebaseAccess: actions.rebaseAccess,
        });

  return (
    <StatusBlock status={status} log={commitLog.log} repository={repository} actions={actions} />
  );
}

const SECTION_CLASS_NAME =
  "grid min-h-28 grid-cols-[auto_minmax(0,1fr)] items-start gap-x-3 border-b px-4 py-3.5";

const HEADING_CLASS_NAME = "font-semibold text-base text-foreground leading-8 tabular-nums";

const TONE_ICON: Record<CommitLogStatusTone, string> = {
  success: "bg-success-surface text-success",
  info: "bg-info-surface text-info",
  warning: "bg-warning-surface text-warning",
  neutral: "bg-content-strong text-foreground-muted",
};

const STATUS_ICON: Record<Exclude<CommitLogStatusIcon, "running">, LucideIcon> = {
  "in-sync": CircleCheckIcon,
  "pending-import": ArrowDownToLineIcon,
  behind: GitBranchIcon,
  warning: TriangleAlertIcon,
  unknown: CircleDashedIcon,
};

interface StatusBlockProps {
  status: CommitLogStatus;
  log: RepositoryCommitLog;
  repository: RepositoryCommitsRepository;
  actions: RepositoryCommitsActions;
}

function StatusBlock({ status, log, repository, actions }: StatusBlockProps) {
  const headingId = React.useId();

  return (
    <section aria-labelledby={headingId} className={SECTION_CLASS_NAME}>
      <StatusIcon tone={status.tone} icon={status.icon} />
      <Col className="min-w-0 gap-2">
        <Row className="flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <Col className="min-w-0 flex-1 basis-md gap-1">
            <h2 id={headingId} className={HEADING_CLASS_NAME}>
              <StatusText parts={status.headline} />
            </h2>
            {status.detail.length > 0 && (
              <p className="max-w-3xl text-foreground text-sm">
                <StatusText parts={status.detail} />
              </p>
            )}
          </Col>
          <RepositoryCommitsStatusActions
            primary={status.primary}
            secondary={status.secondary}
            canRefresh={status.canRefresh}
            condition={log.condition}
            repository={repository}
            actions={actions}
          />
        </Row>
        <Freshness log={log} />
      </Col>
    </section>
  );
}

function LoadingBlock() {
  const headingId = React.useId();

  return (
    <section aria-labelledby={headingId} className={SECTION_CLASS_NAME}>
      <StatusIcon tone="neutral" icon="running" />
      <h2 id={headingId} className={HEADING_CLASS_NAME}>
        Reading the commit log
      </h2>
    </section>
  );
}

function StatusIcon({ tone, icon }: { tone: CommitLogStatusTone; icon: CommitLogStatusIcon }) {
  const Icon = icon === "running" ? null : STATUS_ICON[icon];

  return (
    <span
      className={classNames(
        "flex size-8 shrink-0 items-center justify-center rounded-lg",
        TONE_ICON[tone]
      )}
    >
      {Icon ? <Icon className="size-4" aria-hidden="true" /> : <Spinner />}
    </span>
  );
}

function StatusText({ parts }: { parts: CommitLogTextPart[] }) {
  let offset = 0;

  return parts.map((part) => {
    const text = typeof part === "string" ? part : part.code;
    const key = offset;
    offset += text.length;
    return typeof part === "string" ? (
      <React.Fragment key={key}>{part}</React.Fragment>
    ) : (
      <Ref key={key}>{part.code}</Ref>
    );
  });
}

// The separator ends the previous item, so a wrapped line never starts with one.
const FRESHNESS_ITEM_CLASS_NAME =
  "flex min-w-0 items-center gap-1 after:ml-0.5 after:content-['·'] last:after:content-none";

function Freshness({
  log,
}: {
  log: Pick<RepositoryCommitLog, "git_ref" | "checked_at" | "fetched_at">;
}) {
  const { trackedRef, checkedAt, updatedAt } = getFreshness(log);
  if (!trackedRef && !checkedAt && !updatedAt) return null;

  return (
    <p className="flex flex-wrap items-center gap-x-1.5 text-foreground-muted text-xs tabular-nums">
      {trackedRef && (
        <span className={FRESHNESS_ITEM_CLASS_NAME}>
          Tracking <Ref>{trackedRef}</Ref>
        </span>
      )}
      {checkedAt && (
        <span className={FRESHNESS_ITEM_CLASS_NAME}>
          Remote checked <DateDisplay date={checkedAt} />
        </span>
      )}
      {updatedAt && (
        <span className={FRESHNESS_ITEM_CLASS_NAME}>
          New commits fetched <DateDisplay date={updatedAt} />
        </span>
      )}
    </p>
  );
}

interface ToolbarProps {
  repositoryId: string;
  checkAction: CommitLogAction | null;
  actions: RepositoryCommitsActions;
}

function Toolbar({ repositoryId, checkAction, actions }: ToolbarProps) {
  return (
    <Row className="items-center gap-2 p-2">
      <CommitLogRefreshButton repositoryId={repositoryId} />
      {checkAction && (
        <Row className="ml-auto">
          <CommitLogActionButton
            action={checkAction}
            actions={actions}
            onPress={actions.checkRemote}
          />
        </Row>
      )}
    </Row>
  );
}
