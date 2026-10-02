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
import { TASK_STATE_CRASHED, TASK_STATE_FAILED } from "@/entities/tasks/domain/model/task";
import type { TaskListItem } from "@/entities/tasks/domain/model/task-list-item";
import { getWorkflowLabel } from "@/entities/tasks/domain/model/workflow-labels";
import { getTaskRelatedLabel } from "@/entities/tasks/domain/rules/get-task-related-label";
import { getLogBadge } from "@/entities/tasks/ui/task-display";

export type TaskColumn = "title" | "branch" | "state" | "workflow" | "related" | "updated";

export const ALL_TASK_COLUMNS: TaskColumn[] = [
  "title",
  "branch",
  "state",
  "workflow",
  "related",
  "updated",
];

const COLUMN_HEADERS: Record<TaskColumn, { label: string; className?: string }> = {
  title: { label: "Title" },
  branch: { label: "Branch", className: "w-40" },
  state: { label: "State", className: "w-32" },
  workflow: { label: "Workflow", className: "w-36" },
  related: { label: "Related", className: "w-1/4" },
  updated: { label: "Updated", className: "w-36" },
};

interface TasksTableProps {
  tasks: TaskListItem[];
  totalCount: number;
  page: number;
  onPageChange: (page: number) => void;
  columns?: TaskColumn[];
  /** Names shown instead of the kind label in the Related column, by node id. */
  relatedNames?: ReadonlyMap<string, string>;
  /** Related column text for a task with no related node. */
  emptyRelatedLabel?: string;
}

export function TasksTable({
  tasks,
  totalCount,
  page,
  onPageChange,
  columns = ALL_TASK_COLUMNS,
  relatedNames = new Map(),
  emptyRelatedLabel,
}: TasksTableProps) {
  const totalPages = getTotalPages(totalCount, TABLE_PAGE_SIZE);
  const hasPager = totalPages > 1;

  return (
    <>
      <div
        className="overflow-x-auto"
        data-testid="tasks-table"
        style={hasPager ? { minHeight: (TABLE_PAGE_SIZE + 1) * TABLE_ROW_HEIGHT_PX } : undefined}
      >
        <table className="w-full min-w-190 table-fixed text-sm">
          <thead className="bg-content-muted text-left text-foreground-muted">
            <tr className="border-b">
              {columns.map((column) => (
                <HeaderCell key={column} className={COLUMN_HEADERS[column].className}>
                  {COLUMN_HEADERS[column].label}
                </HeaderCell>
              ))}
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                columns={columns}
                relatedNames={relatedNames}
                emptyRelatedLabel={emptyRelatedLabel}
              />
            ))}
          </tbody>
        </table>
      </div>

      {hasPager && (
        <TablePagination
          className="border-t"
          aria-label="Tasks pagination"
          page={clampPage(page, totalPages)}
          pageSize={TABLE_PAGE_SIZE}
          totalCount={totalCount}
          onPageChange={onPageChange}
        />
      )}
    </>
  );
}

interface TaskRowProps {
  task: TaskListItem;
  columns: TaskColumn[];
  relatedNames: ReadonlyMap<string, string>;
  emptyRelatedLabel?: string;
}

function TaskRow({ task, columns, relatedNames, emptyRelatedLabel }: TaskRowProps) {
  const isFailed = task.state === TASK_STATE_FAILED || task.state === TASK_STATE_CRASHED;

  return (
    <tr className={classNames("h-10 border-b last:border-b-0", isFailed && "bg-danger-surface")}>
      {columns.map((column) => (
        <TaskCell
          key={column}
          column={column}
          task={task}
          relatedNames={relatedNames}
          emptyRelatedLabel={emptyRelatedLabel}
        />
      ))}
    </tr>
  );
}

interface TaskCellProps extends Omit<TaskRowProps, "columns"> {
  column: TaskColumn;
}

function TaskCell({ column, task, relatedNames, emptyRelatedLabel }: TaskCellProps) {
  switch (column) {
    case "title":
      return (
        <td className="px-3">
          <Link
            to={constructPath(`/tasks/${task.id}`)}
            title={task.title}
            className="block truncate rounded-none leading-10"
          >
            {task.title}
          </Link>
        </td>
      );
    case "branch":
      return (
        <td className="truncate px-3 text-foreground-muted" title={task.branch ?? undefined}>
          {task.branch ?? "—"}
        </td>
      );
    case "state":
      return (
        <td className="px-3">
          {(task.state && getLogBadge[task.state]) ?? <Badge variant="gray-outline">UNKNOWN</Badge>}
        </td>
      );
    case "workflow":
      return (
        <td className="truncate px-3 text-foreground-muted" title={task.workflow ?? undefined}>
          {getWorkflowLabel(task.workflow)}
        </td>
      );
    case "related":
      return (
        <RelatedCell
          task={task}
          relatedNames={relatedNames}
          emptyRelatedLabel={emptyRelatedLabel}
        />
      );
    case "updated":
      return (
        <td className="px-3 text-foreground-muted text-xs">
          <DateDisplay date={task.updatedAt} />
        </td>
      );
  }
}

function RelatedCell({ task, relatedNames, emptyRelatedLabel }: Omit<TaskCellProps, "column">) {
  const { schema } = useSchema(task.relatedNodes[0]?.kind);
  const label = getTaskRelatedLabel(
    task,
    relatedNames,
    (kind) => schema?.label || kind,
    emptyRelatedLabel
  );

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
