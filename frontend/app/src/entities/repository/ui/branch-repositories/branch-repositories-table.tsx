import { FolderGitIcon, GitCommitIcon, GitCompareArrowsIcon } from "lucide-react";
import type React from "react";

import { Row } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import { RepositoryRow } from "@/entities/repository/ui/branch-repositories/repository-row";

interface BranchRepositoriesTableProps {
  repositories: BranchRepository[];
  branchName: string;
}

export function BranchRepositoriesTable({
  repositories,
  branchName,
}: BranchRepositoriesTableProps) {
  return (
    <table className="w-full min-w-140 table-fixed text-sm">
      <thead className="bg-content-muted text-left text-foreground-muted">
        <tr className="border-b">
          <HeaderCell icon={<FolderGitIcon className="size-3.5" />}>Repository</HeaderCell>
          <HeaderCell icon={<GitCompareArrowsIcon className="size-3.5" />} className="w-36">
            Git state
          </HeaderCell>
          <HeaderCell icon={<GitCommitIcon className="size-3.5" />} className="w-44">
            Commit
          </HeaderCell>
        </tr>
      </thead>
      <tbody>
        {repositories.map((repository) => (
          <RepositoryRow key={repository.id} repository={repository} branchName={branchName} />
        ))}
      </tbody>
    </table>
  );
}

interface HeaderCellProps {
  children: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}

function HeaderCell({ children, className, icon }: HeaderCellProps) {
  return (
    <th scope="col" className={classNames("h-10 px-3 font-medium text-xs", className)}>
      <Row className="gap-1.5">
        {icon && <span aria-hidden>{icon}</span>}
        {children}
      </Row>
    </th>
  );
}
