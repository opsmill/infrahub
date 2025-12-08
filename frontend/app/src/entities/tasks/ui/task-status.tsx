import { Icon } from "@iconify-icon/react";
import { useQuery } from "@tanstack/react-query";

import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";

import { constructPath } from "@/shared/api/rest/fetch";
import { LinkButton, type LinkButtonProps } from "@/shared/components/buttons/button-primitive";
import { Pulse } from "@/shared/components/ui/pulse";
import { Spinner } from "@/shared/components/ui/spinner";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { QSP } from "@/shared/config/qsp";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { isTaskRunningOnBranchQueryOptions } from "@/entities/tasks/domain/is-task-running-on-branch/is-task-running-on-branch.query";

export function TaskStatus() {
  const { currentBranch } = useCurrentBranch();

  const {
    error,
    isPending,
    data: isTaskRunningOnBranch,
  } = useQuery({
    ...isTaskRunningOnBranchQueryOptions(currentBranch.name),
    refetchInterval: 10_000,
  });

  const filter = {
    name: "branch__value",
    value: currentBranch.name,
  };

  const commonButtonProps: LinkButtonProps = {
    size: "square",
    variant: "ghost",
    className:
      "h-8 w-8 bg-neutral-50 border border-neutral-200 rounded-lg relative shrink-0 dark:bg-gray-700 dark:border-gray-600",
    to: constructPath("/tasks", [{ name: QSP.FILTER, value: JSON.stringify([filter]) }]),
  };

  if (error) {
    const tooltipContent = "Error checking task status";
    return (
      <Tooltip enabled content={tooltipContent}>
        <LinkButton {...commonButtonProps} aria-label={tooltipContent}>
          <Icon icon="mdi:error-outline" className="text-red-500" />
        </LinkButton>
      </Tooltip>
    );
  }

  const tooltipContent = isTaskRunningOnBranch
    ? "Tasks running on this branch"
    : "View branch tasks";

  return (
    <Tooltip enabled content={tooltipContent}>
      <LinkButton {...commonButtonProps} aria-label={tooltipContent}>
        {isPending ? (
          <Spinner />
        ) : (
          <TasksStatusIcon className="text-slate-700 dark:text-slate-300" />
        )}
        {isTaskRunningOnBranch && (
          <Pulse className="right-[6.5px] bottom-[6.5px]" data-testid="pulse" />
        )}
      </LinkButton>
    </Tooltip>
  );
}
