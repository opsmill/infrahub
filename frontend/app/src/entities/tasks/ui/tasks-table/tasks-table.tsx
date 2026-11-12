import type React from "react";

import { DateDisplay } from "@/shared/components/display/date-display";
import { Badge } from "@/shared/components/ui/badge";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { TASK_STATE_CRASHED, TASK_STATE_FAILED } from "@/entities/tasks/domain/model/task";
import type { TaskListItem } from "@/entities/tasks/domain/model/task-list-item";
import { getTaskRelatedLabel } from "@/entities/tasks/domain/rules/get-task-related-label";
import { getWorkflowLabel } from "@/entities/tasks/domain/rules/get-workflow-label";
import { getTaskDetailsUrl } from "@/entities/tasks/ui/routing/task-urls";
import { getLogBadge } from "@/entities/tasks/ui/task-display";

interface TasksTableProps {
  tasks: TaskListItem[];
  /** Names shown instead of the kind label in the Related column, by node id. */
  relatedNames: ReadonlyMap<string, string>;
  /** Related column text for a task with no related node. */
  emptyRelatedLabel: string;
}

export function TasksTable({ tasks, relatedNames, emptyRelatedLabel }: TasksTableProps) {
  return (
    <table className="w-full min-w-190 table-fixed text-sm">
      <thead className="bg-content-muted text-left text-foreground-muted">
        <tr className="border-b">
          <HeaderCell>Title</HeaderCell>
          <HeaderCell className="w-32">State</HeaderCell>
          <HeaderCell className="w-36">Workflow</HeaderCell>
          <HeaderCell className="w-1/4">Related</HeaderCell>
          <HeaderCell className="w-36">Updated</HeaderCell>
        </tr>
      </thead>
      <tbody>
        {tasks.map((task) => (
          <TaskRow
            key={task.id}
            task={task}
            relatedNames={relatedNames}
            emptyRelatedLabel={emptyRelatedLabel}
          />
        ))}
      </tbody>
    </table>
  );
}

interface TaskRowProps {
  task: TaskListItem;
  relatedNames: ReadonlyMap<string, string>;
  emptyRelatedLabel: string;
}

function TaskRow({ task, relatedNames, emptyRelatedLabel }: TaskRowProps) {
  const isFailed = task.state === TASK_STATE_FAILED || task.state === TASK_STATE_CRASHED;

  return (
    <tr className={classNames("h-10 border-b last:border-b-0", isFailed && "bg-danger-surface")}>
      <td className="px-3">
        <Link
          to={getTaskDetailsUrl(task.id)}
          title={task.title}
          className="block truncate rounded-none leading-10"
        >
          {task.title}
        </Link>
      </td>
      <td className="px-3">
        {(task.state && getLogBadge[task.state]) ?? <Badge variant="gray-outline">UNKNOWN</Badge>}
      </td>
      <td className="truncate px-3 text-foreground-muted" title={task.workflow ?? undefined}>
        {getWorkflowLabel(task.workflow)}
      </td>
      <RelatedCell task={task} relatedNames={relatedNames} emptyRelatedLabel={emptyRelatedLabel} />
      <td className="px-3 text-foreground-muted text-xs">
        <DateDisplay date={task.updatedAt} />
      </td>
    </tr>
  );
}

function RelatedCell({ task, relatedNames, emptyRelatedLabel }: TaskRowProps) {
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
