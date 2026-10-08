import { LinkButton, Tooltip } from "@infrahub/ui";
import { ExternalLinkIcon } from "lucide-react";

import { PagedTableCard } from "@/shared/components/table/paged-table-card";
import { useTablePagination } from "@/shared/hooks/use-table-pagination";

import { useGetRepositoryNames } from "@/entities/repository/ui/queries/get-repository-names.query";
import { TASK_STATE_FAILED } from "@/entities/tasks/domain/model/task";
import type { TaskListPage } from "@/entities/tasks/domain/model/task-list-item";
import { getRelatedNodeIds } from "@/entities/tasks/domain/rules/get-related-node-ids";
import {
  useGetBranchFailedTaskCount,
  useGetBranchTasks,
} from "@/entities/tasks/ui/queries/get-branch-tasks.query";
import { getTasksPageUrl } from "@/entities/tasks/ui/routing/task-urls";
import { TasksTable } from "@/entities/tasks/ui/tasks-table/tasks-table";

const TASKS_URL_KEY = "tasks";

interface BranchTasksCardProps {
  branchName: string;
}

export function BranchTasksCard({ branchName }: BranchTasksCardProps) {
  const { page, setPage, pageSize } = useTablePagination({ urlKey: TASKS_URL_KEY });
  const query = useGetBranchTasks({ branchName, page, pageSize });
  const { data: failedCount } = useGetBranchFailedTaskCount({ branchName });

  return (
    <PagedTableCard
      title="Tasks"
      itemName={{ one: "task", other: "tasks" }}
      query={query}
      page={page}
      pageSize={pageSize}
      onPageChange={setPage}
      headerActions={
        <>
          {!!failedCount && (
            <Tooltip message="Failed tasks on this branch, including runs retried since.">
              <LinkButton
                href={getTasksPageUrl(branchName, [
                  { name: "state__value", value: TASK_STATE_FAILED },
                ])}
                variant="ghost"
                size="xs"
                className="font-normal text-danger text-xs tabular-nums"
              >
                {failedCount} failed
              </LinkButton>
            </Tooltip>
          )}
          <LinkButton
            href={getTasksPageUrl(branchName, [])}
            variant="ghost"
            size="xs"
            className="ml-auto text-xs"
          >
            Open in Tasks <ExternalLinkIcon className="size-3" aria-hidden />
          </LinkButton>
        </>
      }
      failedMessage="Task results didn't load."
      emptyTitle="No tasks"
      emptyMessage="No tasks have run on this branch yet. Imports, generators and validations appear here as they run."
      renderTable={(data) => <BranchTasksTable data={data} branchName={branchName} />}
      tableTestId="tasks-table"
      data-testid="branch-tasks-card"
    />
  );
}

// Only the repositories on the page shown are looked up, by id.
function BranchTasksTable({ data, branchName }: { data: TaskListPage; branchName: string }) {
  const { data: repositoryNames } = useGetRepositoryNames({
    branchName,
    ids: getRelatedNodeIds(data.tasks),
  });

  return (
    <TasksTable
      tasks={data.tasks}
      relatedNames={new Map(Object.entries(repositoryNames ?? {}))}
      emptyRelatedLabel="This branch"
    />
  );
}
