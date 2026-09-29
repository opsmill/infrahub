import { Card, CardHeader, LinkButton, Tooltip } from "@infrahub/ui";
import { ExternalLinkIcon } from "lucide-react";

import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/ui/badge";
import { QSP } from "@/shared/config/qsp";
import { usePageInRange } from "@/shared/hooks/usePageInRange";
import { getTotalPages, TABLE_PAGE_SIZE } from "@/shared/utils/table-pagination";

import { getBranchQspOverride } from "@/entities/branches/ui/routing/branch-urls";
import { TASK_STATE_FAILED } from "@/entities/tasks/domain/model/task";
import type { TaskListPage } from "@/entities/tasks/domain/model/task-list-item";
import {
  BranchTasksFailed,
  BranchTasksLoading,
  BranchTasksNone,
} from "@/entities/tasks/ui/branch-tasks/branch-tasks-states";
import {
  useGetBranchFailedTaskCount,
  useGetBranchTasks,
} from "@/entities/tasks/ui/queries/get-branch-tasks.query";
import { type TaskColumn, TasksTable } from "@/entities/tasks/ui/tasks-table/tasks-table";

const BRANCH_TASK_COLUMNS: TaskColumn[] = ["title", "state", "workflow", "related", "updated"];

interface BranchTasksCardProps {
  branchName: string;
  isDefaultBranch: boolean;
  page: number;
  onPageChange: (page: number) => void;
  repositoryNames: ReadonlyMap<string, string>;
}

function getTasksPageUrl(
  branchName: string,
  isDefaultBranch: boolean,
  filters: { name: string; value: string }[]
) {
  return constructPath("/tasks", [
    getBranchQspOverride(branchName, isDefaultBranch),
    {
      name: QSP.FILTER,
      value: JSON.stringify([{ name: "branch__value", value: branchName }, ...filters]),
    },
  ]);
}

export function BranchTasksCard({
  branchName,
  isDefaultBranch,
  page,
  onPageChange,
  repositoryNames,
}: BranchTasksCardProps) {
  const { data, isPending } = useGetBranchTasks({ branchName, page });
  const { data: failedCount } = useGetBranchFailedTaskCount({ branchName });
  usePageInRange(page, data ? getTotalPages(data.count, TABLE_PAGE_SIZE) : null, onPageChange);

  return (
    <Card className="overflow-hidden" data-testid="branch-tasks-card">
      <CardHeader className="flex items-center gap-2">
        <h2>Tasks</h2>
        {data && (
          <Badge variant="blue" className="rounded-full font-normal tabular-nums">
            {data.count}
          </Badge>
        )}
        {!!failedCount && (
          <Tooltip message="Failed tasks on this branch, including runs retried since.">
            <LinkButton
              href={getTasksPageUrl(branchName, isDefaultBranch, [
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
          href={getTasksPageUrl(branchName, isDefaultBranch, [])}
          variant="ghost"
          size="xs"
          className="ml-auto text-xs"
        >
          Open in Tasks <ExternalLinkIcon className="size-3" aria-hidden />
        </LinkButton>
      </CardHeader>

      <BranchTasksBody
        data={data}
        isPending={isPending}
        page={page}
        onPageChange={onPageChange}
        repositoryNames={repositoryNames}
      />
    </Card>
  );
}

interface BranchTasksBodyProps
  extends Pick<BranchTasksCardProps, "page" | "onPageChange" | "repositoryNames"> {
  data: TaskListPage | undefined;
  isPending: boolean;
}

function BranchTasksBody({
  data,
  isPending,
  page,
  onPageChange,
  repositoryNames,
}: BranchTasksBodyProps) {
  if (isPending) return <BranchTasksLoading />;
  if (!data) return <BranchTasksFailed />;
  if (data.count === 0) return <BranchTasksNone />;

  return (
    <TasksTable
      tasks={data.tasks}
      totalCount={data.count}
      page={page}
      onPageChange={onPageChange}
      columns={BRANCH_TASK_COLUMNS}
      relatedNames={repositoryNames}
      emptyRelatedLabel="This branch"
    />
  );
}
