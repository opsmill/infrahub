import { LinkButton } from "@/components/buttons/button-primitive";
import { Pulse } from "@/components/ui/pulse";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import { TASKS_STATUS_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { TASKS_STATUS } from "@/graphql/queries/tasks/getTasksStatus";
import useQuery from "@/hooks/useQuery";
import TasksStatusIcon from "@/images/icons/tasks-status.svg?react";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";

export function TaskStatus() {
  const branch = useAtomValue(currentBranchAtom);

  const { error, loading, data } = useQuery(TASKS_STATUS, {
    variables: { branch: branch?.name },
    skip: !branch?.name,
    pollInterval: 10_000,
  });

  if (error) {
    return <Icon icon="mdi:error-outline" className="text-red-500" />;
  }

  const count = data && data[TASKS_STATUS_OBJECT]?.count;

  const filter = {
    name: "branch__value",
    value: branch?.name,
  };

  return (
    <Tooltip enabled content="Task">
      <LinkButton
        size="square"
        variant="ghost"
        className="h-8 w-8 bg-neutral-50 border border-neutral-200 rounded-lg relative"
        to={constructPath("/tasks", [{ name: QSP.FILTER, value: JSON.stringify([filter]) }])}
      >
        {loading && <Spinner />}

        {!loading && <TasksStatusIcon />}

        {!loading && count > 0 && <Pulse className="right-[6.5px] bottom-[6.5px]" />}
      </LinkButton>
    </Tooltip>
  );
}
