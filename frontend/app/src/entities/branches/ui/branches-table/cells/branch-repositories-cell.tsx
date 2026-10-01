import { Spinner, Tooltip } from "@infrahub/ui";
import { FolderGitIcon } from "lucide-react";
import { Link } from "react-router";

import { Row } from "@/shared/components/container";
import { TableCell } from "@/shared/components/table/table-cell";
import { LinkPill } from "@/shared/components/ui/link-pill";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import {
  getBranchDetailsUrl,
  getBranchQspOverride,
} from "@/entities/branches/ui/routing/branch-urls";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import { rankRepositories } from "@/entities/repository/domain/rules/rank-repositories";
import { useGetBranchRepositories } from "@/entities/repository/ui/queries/get-branch-repositories.query";

const SHORT_COMMIT_LENGTH = 7;

interface BranchRepositoriesCellProps {
  branch: BranchListItem;
}

export function BranchRepositoriesCell({ branch }: BranchRepositoriesCellProps) {
  return (
    <TableCell className="h-auto min-h-14">
      <BranchRepositoriesCellContent branch={branch} />
    </TableCell>
  );
}

function BranchRepositoriesCellContent({ branch }: BranchRepositoriesCellProps) {
  const { data, isPending, error } = useGetBranchRepositories({
    branchName: branch.name,
    syncWithGit: Boolean(branch.sync_with_git),
  });

  if (isPending) return <Spinner />;

  if (error) {
    return (
      <>
        <Tooltip message={error.message} nonInteractiveTrigger>
          <span className="text-foreground-muted">Could not load repositories</span>
        </Tooltip>
        <span className="sr-only">{error.message}</span>
      </>
    );
  }

  if (data.status === "denied") {
    return <span className="text-foreground-muted">No permission</span>;
  }

  const [first, ...others] = rankRepositories(data.repositories);

  if (!first) {
    return (
      <span className="text-foreground-muted">
        {branch.sync_with_git ? "No repositories" : "Not synced with Git"}
      </span>
    );
  }

  const href = getObjectDetailsUrl(first.kind, first.id, [
    getBranchQspOverride(branch.name, Boolean(branch.is_default)),
  ]);

  return (
    <Row className="flex-wrap">
      <Tooltip message={getRepositorySummary(first)}>
        <LinkPill href={href} className="max-w-40">
          <FolderGitIcon className="shrink-0 text-accent" aria-hidden />
          <span className="truncate">{first.name}</span>
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

function getRepositorySummary({ syncStatus, commit, isReadOnly }: BranchRepository): string {
  return [
    syncStatus.label || syncStatus.value,
    commit?.slice(0, SHORT_COMMIT_LENGTH),
    isReadOnly && "read-only",
  ]
    .filter(Boolean)
    .join(" · ");
}
