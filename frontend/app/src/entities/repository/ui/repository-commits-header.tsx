import { TriangleAlertIcon } from "lucide-react";

import { Col, Row } from "@/shared/components/container";
import { DateDisplay } from "@/shared/components/display/date-display";
import { pluralize } from "@/shared/utils/string";

import {
  REPOSITORY_GIT_CONDITION,
  type RepositoryCommitLog,
} from "@/entities/repository/domain/model/repository";

export interface RepositoryCommitsHeaderProps {
  log: RepositoryCommitLog;
}

export function RepositoryCommitsHeader({ log }: RepositoryCommitsHeaderProps) {
  return (
    <Col className="gap-1.5 px-2 py-2">
      <FreshnessLine log={log} />
      <ConditionNotice log={log} />
    </Col>
  );
}

function FreshnessLine({ log }: RepositoryCommitsHeaderProps) {
  const { gitRef, checkedAt, fetchedAt } = log;
  const showFetchedAt = fetchedAt !== null && fetchedAt !== checkedAt;

  return (
    <p className="flex flex-wrap items-center gap-x-1.5 text-foreground-muted text-sm">
      {gitRef && (
        <span className="flex items-center gap-1">
          Tracking <code className="font-mono text-foreground text-xs">{gitRef}</code>
        </span>
      )}
      {checkedAt && (
        <span className="flex items-center gap-1">
          Checked <DateDisplay date={checkedAt} fullTimestamp className="text-sm" />
        </span>
      )}
      {showFetchedAt && (
        <span className="flex items-center gap-1">
          Updated <DateDisplay date={fetchedAt} fullTimestamp className="text-sm" />
        </span>
      )}
    </p>
  );
}

const REWRITTEN_NOTICE =
  "The tracked ref was rewritten. The imported commit is no longer part of its history, so nothing is reported as pending.";
const ORPHANED_NOTICE = "The imported commit could not be found on the remote.";

function ConditionNotice({ log }: RepositoryCommitsHeaderProps) {
  const { condition, pendingCount } = log;

  if (condition === REPOSITORY_GIT_CONDITION.REWRITTEN) {
    return <AmberNotice>{REWRITTEN_NOTICE}</AmberNotice>;
  }

  if (condition === REPOSITORY_GIT_CONDITION.ORPHANED) {
    return <AmberNotice>{ORPHANED_NOTICE}</AmberNotice>;
  }

  if (condition === REPOSITORY_GIT_CONDITION.BEHIND && pendingCount !== null) {
    return (
      <p className="font-medium text-sm">{pluralize(pendingCount, "commit")} pending import</p>
    );
  }

  return null;
}

function AmberNotice({ children }: { children: string }) {
  return (
    <Row
      role="note"
      className="rounded-md bg-amber-50 px-3 py-2 text-amber-800 text-sm dark:bg-amber-200/10 dark:text-amber-200"
    >
      <TriangleAlertIcon className="size-4 shrink-0" aria-hidden="true" />
      <p>{children}</p>
    </Row>
  );
}
