import { Card, CardHeader, LinkButton, Tooltip } from "@infrahub/ui";
import { ExternalLinkIcon } from "lucide-react";

import { constructPath } from "@/shared/api/rest/fetch";
import { CELL_HEIGHT_PX } from "@/shared/components/table/style";
import { TablePagination } from "@/shared/components/table/table-pagination";
import { Badge } from "@/shared/components/ui/badge";
import { QSP } from "@/shared/config/qsp";
import { useTablePagination } from "@/shared/hooks/use-table-pagination";
import { PAGE_SIZE } from "@/shared/utils/table-pagination";

import { getBranchQsp } from "@/entities/branches/ui/routing/branch-urls";
import { useGetRepositoryNames } from "@/entities/repository/ui/queries/get-repository-names.query";
import { TASK_STATE_FAILED } from "@/entities/tasks/domain/model/task";
import type { TaskListPage } from "@/entities/tasks/domain/model/task-list-item";
import { getRelatedNodeIds } from "@/entities/tasks/domain/rules/get-related-node-ids";
import {
  BranchTasksFailed,
  BranchTasksLoading,
  BranchTasksNone,
} from "@/entities/tasks/ui/branch-tasks/branch-tasks-states";
import {
  useGetBranchFailedTaskCount,
  useGetBranchTasks,
} from "@/entities/tasks/ui/queries/get-branch-tasks.query";
import { TasksTable } from "@/entities/tasks/ui/tasks-table/tasks-table";

export const TASKS_URL_KEY = "tasks";

interface BranchTasksCardProps {
  branchName: string;
}

function getTasksPageUrl(branchName: string, filters: { name: string; value: string }[]) {
  return constructPath("/tasks", [
    getBranchQsp(branchName),
    {
      name: QSP.FILTER,
      value: JSON.stringify([{ name: "branch__value", value: branchName }, ...filters]),
    },
  ]);
}

export function BranchTasksCard({ branchName }: BranchTasksCardProps) {
  const { page, setPage, pageSize } = useTablePagination({ urlKey: TASKS_URL_KEY });
  const { page: currentPage, query } = useGetBranchTasks({ branchName, page, pageSize });
  const { data: failedCount } = useGetBranchFailedTaskCount({ branchName });

  return (
    <Card className="overflow-hidden" data-testid="branch-tasks-card">
      <CardHeader className="flex items-center gap-2">
        <h2>Tasks</h2>
        {query.data && (
          <Badge variant="blue" className="rounded-full font-normal tabular-nums">
            {query.data.count}
          </Badge>
        )}
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
      </CardHeader>

      <BranchTasksBody
        data={query.data}
        isPending={query.isPending}
        branchName={branchName}
        page={currentPage}
        onPageChange={setPage}
      />
    </Card>
  );
}

interface BranchTasksBodyProps {
  data: TaskListPage | undefined;
  isPending: boolean;
  branchName: string;
  page: number;
  onPageChange: (page: number) => void;
}

function BranchTasksBody({
  data,
  isPending,
  branchName,
  page,
  onPageChange,
}: BranchTasksBodyProps) {
  if (isPending) return <BranchTasksLoading />;
  if (!data) return <BranchTasksFailed />;
  if (data.count === 0) return <BranchTasksNone />;

  // A short last page would otherwise shrink the card and move everything below it.
  const hasMultiplePages = data.count > PAGE_SIZE;

  return (
    <>
      <div
        className="overflow-x-auto"
        data-testid="tasks-table"
        style={hasMultiplePages ? { minHeight: (PAGE_SIZE + 1) * CELL_HEIGHT_PX } : undefined}
      >
        <BranchTasksTable data={data} branchName={branchName} />
      </div>

      {hasMultiplePages && (
        <TablePagination
          className="border-t"
          aria-label="Tasks pagination"
          page={page}
          pageSize={PAGE_SIZE}
          totalCount={data.count}
          onPageChange={onPageChange}
        />
      )}
    </>
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
