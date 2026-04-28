import { Icon } from "@iconify-icon/react";
import { useQuery } from "@tanstack/react-query";

import TasksStatusIcon from "@/assets/icons/tasks-status.svg?react";

import { constructPath } from "@/shared/api/rest/fetch";
import { LinkButton, type LinkButtonProps } from "@/shared/components/aria/button";
import { Tooltip } from "@/shared/components/aria/tooltip";
import { Pulse } from "@/shared/components/ui/pulse";
import { Spinner } from "@/shared/components/ui/spinner";
import { QSP } from "@/shared/config/qsp";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { isTaskRunningOnBranchQueryOptions } from "@/entities/tasks/ui/queries/is-task-running-on-branch.query";

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
    shape: "square",
    variant: "outline",
    size: "sm",
    href: constructPath("/tasks", [{ name: QSP.FILTER, value: JSON.stringify([filter]) }]),
  };

  if (error) {
    const tooltipContent = "Error checking task status";
    return (
      <Tooltip message={tooltipContent}>
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
    <Tooltip message={tooltipContent}>
      <LinkButton {...commonButtonProps} aria-label={tooltipContent}>
        {isPending ? <Spinner /> : <TasksStatusIcon />}
        {isTaskRunningOnBranch && (
          <Pulse className="right-[6.5px] bottom-[6.5px]" data-testid="pulse" />
        )}
      </LinkButton>
    </Tooltip>
  );
}
