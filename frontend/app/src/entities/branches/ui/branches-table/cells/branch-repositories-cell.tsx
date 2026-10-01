import { Spinner, Tooltip } from "@infrahub/ui";
import { FolderGitIcon } from "lucide-react";
import { Link } from "react-router";

import { Row } from "@/shared/components/container";
import { TableCell } from "@/shared/components/table/table-cell";
import { LinkPill } from "@/shared/components/ui/link-pill";

import { formatRepositoryState } from "@/entities/branches/domain/rules/format-repository-summary";
import type { BranchTableRow } from "@/entities/branches/ui/branches-table/branch-table-row";
import {
  getBranchDetailsUrl,
  getBranchQspOverride,
} from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";

interface BranchRepositoriesCellProps {
  branch: BranchTableRow;
}

export function BranchRepositoriesCell({ branch }: BranchRepositoriesCellProps) {
  return (
    <TableCell className="h-auto min-h-14">
      <BranchRepositoriesCellContent branch={branch} />
    </TableCell>
  );
}

function BranchRepositoriesCellContent({ branch }: BranchRepositoriesCellProps) {
  const summary = branch.repositorySummary;

  if (summary.status === "pending") return <Spinner />;

  if (summary.status === "denied") {
    return <span className="text-foreground-muted">No permission</span>;
  }

  if (summary.status === "error") {
    return (
      <>
        <Tooltip message={summary.message} nonInteractiveTrigger>
          <span className="text-foreground-muted">Could not load repositories</span>
        </Tooltip>
        <span className="sr-only">{summary.message}</span>
      </>
    );
  }

  const [first, ...others] = summary.repositories;

  if (!first) {
    return (
      <span className="text-foreground-muted">
        {branch.sync_with_git ? "No repositories" : "Not synced with Git"}
      </span>
    );
  }

  const { repository } = first;
  const href = getObjectDetailsUrl(repository.kind, repository.id, [
    getBranchQspOverride(branch.name, Boolean(branch.is_default)),
  ]);

  return (
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
          className="shrink-0 whitespace-nowrap text-foreground-muted text-sm hover:underline"
        >
          +{others.length} more
        </Link>
      )}
    </Row>
  );
}
