import type React from "react";

import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import { TablePagination } from "@/shared/components/table/table-pagination";
import { Badge } from "@/shared/components/ui/badge";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";
import {
  clampPage,
  getTotalPages,
  TABLE_PAGE_SIZE,
  TABLE_ROW_HEIGHT_PX,
} from "@/shared/utils/table-pagination";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import type { BranchTask } from "@/entities/tasks/domain/model/branch-task";
import { TASK_STATE_CRASHED, TASK_STATE_FAILED } from "@/entities/tasks/domain/model/task";
import { getWorkflowLabel } from "@/entities/tasks/domain/model/workflow-labels";
import { getTaskRelatedLabel } from "@/entities/tasks/domain/rules/get-task-related-label";
import { getLogBadge } from "@/entities/tasks/ui/task-display";

interface BranchTasksTableProps {
  tasks: BranchTask[];
  totalCount: number;
  page: number;
  onPageChange: (page: number) => void;
  repositoryNames: ReadonlyMap<string, string>;
}

export function BranchTasksTable({
  tasks,
  totalCount,
  page,
  onPageChange,
  repositoryNames,
}: BranchTasksTableProps) {
  const totalPages = getTotalPages(totalCount, TABLE_PAGE_SIZE);
  const hasPager = totalPages > 1;

  return (
    <>
      <div
        className="overflow-x-auto"
        data-testid="branch-tasks-table"
        style={hasPager ? { minHeight: (TABLE_PAGE_SIZE + 1) * TABLE_ROW_HEIGHT_PX } : undefined}
      >
        <table className="w-full min-w-190 table-fixed text-sm">
          <thead className="bg-content-muted text-left text-foreground-muted">
            <tr className="border-b">
              <HeaderCell>Title</HeaderCell>
              <HeaderCell className="w-32">State</HeaderCell>
              <HeaderCell className="w-28">Workflow</HeaderCell>
              <HeaderCell className="w-1/4">Related</HeaderCell>
              <HeaderCell className="w-36">Updated</HeaderCell>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <BranchTaskRow key={task.id} task={task} repositoryNames={repositoryNames} />
            ))}
          </tbody>
        </table>
      </div>

      {hasPager && (
        <TablePagination
          className="border-t"
          page={clampPage(page, totalPages)}
          pageSize={TABLE_PAGE_SIZE}
          totalCount={totalCount}
          onPageChange={onPageChange}
        />
      )}
    </>
  );
}

interface BranchTaskRowProps {
  task: BranchTask;
  repositoryNames: ReadonlyMap<string, string>;
}

function BranchTaskRow({ task, repositoryNames }: BranchTaskRowProps) {
  const isFailed = task.state === TASK_STATE_FAILED || task.state === TASK_STATE_CRASHED;

  return (
    <tr className={classNames("h-10 border-b last:border-b-0", isFailed && "bg-danger-surface")}>
      <td className="px-3">
        <Link
          to={constructPath(`/tasks/${task.id}`)}
          title={task.title}
          className="block truncate rounded-none leading-10"
        >
          {task.title}
        </Link>
      </td>
      <td className="px-3">
        {(task.state && getLogBadge[task.state]) ?? <Badge variant="gray-outline">UNKNOWN</Badge>}
      </td>
      <td className="truncate px-3 text-foreground-muted">{getWorkflowLabel(task.workflow)}</td>
      <RelatedCell task={task} repositoryNames={repositoryNames} />
      <td className="px-3 text-foreground-muted text-xs">
        <DateDisplay date={task.updatedAt} />
      </td>
    </tr>
  );
}

function RelatedCell({ task, repositoryNames }: BranchTaskRowProps) {
  const { schema } = useSchema(task.relatedNodes[0]?.kind);
  const label = getTaskRelatedLabel(task, repositoryNames, (kind) => schema?.label || kind);

  return (
    <td className="truncate px-3 text-foreground-muted" title={label}>
      {label}
    </td>
  );
}

interface HeaderCellProps {
  children: React.ReactNode;
  className?: string;
}

function HeaderCell({ children, className }: HeaderCellProps) {
  return (
    <th scope="col" className={classNames("h-10 px-3 font-medium text-xs", className)}>
      {children}
    </th>
  );
}
