import { Spinner, Tooltip } from "@infrahub/ui";
import { FolderGitIcon } from "lucide-react";
import { Link } from "react-router";

import { Col, Row } from "@/shared/components/container";
import { TableCell } from "@/shared/components/table/table-cell";
import { LinkPill } from "@/shared/components/ui/link-pill";
import { classNames } from "@/shared/utils/common";

import type { FailedRepository } from "@/entities/branch-git-status/domain/model/branch-git-status";
import {
  formatFailedRepositoryCount,
  formatFailedRepositoryReasons,
  formatRepositoryState,
} from "@/entities/branch-git-status/domain/rules/format-branch-git-status";
import type { BranchTableRow } from "@/entities/branches/ui/branches-table/branch-table-row";
import { getBranchDetailsUrl, getBranchQsp } from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";

interface BranchRepositoriesCellProps {
  branch: BranchTableRow;
}

export function BranchRepositoriesCell({ branch }: BranchRepositoriesCellProps) {
  return (
    <TableCell className="h-auto min-h-14" data-testid={`branch-repositories-cell-${branch.name}`}>
      <BranchRepositoriesCellContent branch={branch} />
    </TableCell>
  );
}

function RepositoriesLoading() {
  // Every row loads at once, so a live status region per row would announce the same thing many times.
  return (
    <>
      <Spinner aria-hidden />
      <span className="sr-only">Loading repositories</span>
    </>
  );
}

interface TextWithReasonProps {
  text: string;
  reason: string;
  className?: string;
}

function TextWithReason({ text, reason, className }: TextWithReasonProps) {
  return (
    <>
      <Tooltip message={reason} nonInteractiveTrigger>
        <span className={classNames("text-foreground-muted", className)}>{text}</span>
      </Tooltip>
      <span className="sr-only">{reason}</span>
    </>
  );
}

function FailedRepositoriesNotice({ failed }: { failed: readonly FailedRepository[] }) {
  return (
    <TextWithReason
      text={formatFailedRepositoryCount(failed.length)}
      reason={formatFailedRepositoryReasons(failed)}
      className="text-xs"
    />
  );
}

function BranchRepositoriesCellContent({ branch }: BranchRepositoriesCellProps) {
  const { gitStatus } = branch;

  if (gitStatus.status === "pending") return <RepositoriesLoading />;

  if (gitStatus.status === "denied") {
    return <span className="text-foreground-muted">No permission</span>;
  }

  if (gitStatus.status === "error") {
    return <TextWithReason text="Could not load repositories" reason={gitStatus.message} />;
  }

  const failed = gitStatus.unloaded.filter(
    (repository): repository is FailedRepository => repository.status !== "pending"
  );
  const [first, ...others] = gitStatus.repositories;

  if (!first) {
    if (gitStatus.unloaded.some(({ status }) => status === "pending")) {
      return <RepositoriesLoading />;
    }
    if (failed.length > 0) return <FailedRepositoriesNotice failed={failed} />;
    return (
      <span className="text-foreground-muted">
        {branch.sync_with_git ? "No repositories" : "Not synced with Git"}
      </span>
    );
  }

  const { repository } = first;
  const href = getObjectDetailsUrl(repository.kind, repository.id, [getBranchQsp(branch.name)]);
  const moreLabel = `+${others.length} more ${others.length === 1 ? "repository" : "repositories"} on ${branch.name}`;

  return (
    <Col className="items-start gap-1">
      <Row className="flex-wrap">
        <Tooltip message={formatRepositoryState(first)}>
          <LinkPill href={href} className="max-w-40">
            <FolderGitIcon className="shrink-0 text-accent" aria-hidden />
            <span className="truncate">{repository.name}</span>
          </LinkPill>
        </Tooltip>

        {others.length > 0 && (
          <Link
            to={getBranchDetailsUrl(branch.name)}
            aria-label={moreLabel}
            className="shrink-0 whitespace-nowrap text-foreground-muted text-sm hover:underline"
          >
            +{others.length} more
          </Link>
        )}
      </Row>

      {failed.length > 0 && <FailedRepositoriesNotice failed={failed} />}
    </Col>
  );
}
