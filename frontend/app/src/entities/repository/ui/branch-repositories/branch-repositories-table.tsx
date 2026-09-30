import { FolderGitIcon, GitCommitIcon } from "lucide-react";
import type React from "react";

import { TablePagination } from "@/shared/components/table/table-pagination";
import { usePageInRange } from "@/shared/hooks/usePageInRange";
import { classNames } from "@/shared/utils/common";
import {
  clampPage,
  getTotalPages,
  TABLE_PAGE_SIZE,
  TABLE_ROW_HEIGHT_PX,
} from "@/shared/utils/table-pagination";

import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import { rankRepositories } from "@/entities/repository/domain/rules/rank-repositories";
import { RepositoryRow } from "@/entities/repository/ui/branch-repositories/repository-row";

interface BranchRepositoriesTableProps {
  repositories: BranchRepository[];
  branchName: string;
  isDefaultBranch: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

export function BranchRepositoriesTable({
  repositories,
  branchName,
  isDefaultBranch,
  page,
  onPageChange,
}: BranchRepositoriesTableProps) {
  const ranked = rankRepositories(repositories);
  const totalPages = getTotalPages(ranked.length, TABLE_PAGE_SIZE);
  const currentPage = clampPage(page, totalPages);
  const rows = ranked.slice((currentPage - 1) * TABLE_PAGE_SIZE, currentPage * TABLE_PAGE_SIZE);
  const hasPager = totalPages > 1;
  usePageInRange(page, totalPages, onPageChange);

  return (
    <>
      <div
        className="overflow-x-auto"
        data-testid="branch-repositories-table"
        style={hasPager ? { minHeight: (TABLE_PAGE_SIZE + 1) * TABLE_ROW_HEIGHT_PX } : undefined}
      >
        <table className="w-full min-w-140 table-fixed text-sm">
          <thead className="bg-content-muted text-left text-foreground-muted">
            <tr className="border-b">
              <HeaderCell icon={<FolderGitIcon className="size-3.5" />}>Repository</HeaderCell>
              <HeaderCell className="w-36">Git state</HeaderCell>
              <HeaderCell icon={<GitCommitIcon className="size-3.5" />} className="w-44">
                Commit
              </HeaderCell>
            </tr>
          </thead>
          <tbody>
            {rows.map((repository) => (
              <RepositoryRow
                key={repository.id}
                repository={repository}
                branchName={branchName}
                isDefaultBranch={isDefaultBranch}
              />
            ))}
          </tbody>
        </table>
      </div>

      {hasPager && (
        <TablePagination
          className="border-t"
          page={currentPage}
          pageSize={TABLE_PAGE_SIZE}
          totalCount={ranked.length}
          onPageChange={onPageChange}
        />
      )}
    </>
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
      <span className="flex items-center gap-1.5">
        {icon && <span aria-hidden>{icon}</span>}
        {children}
      </span>
    </th>
  );
}
