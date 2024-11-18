import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { Pulse } from "@/components/ui/pulse";
import { Spinner } from "@/components/ui/spinner";
import { TASKS_STATUS_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { TASKS_STATUS } from "@/graphql/queries/tasks/getTasksStatus";
import useQuery from "@/hooks/useQuery";
import { ReactComponent as TasksStatusIcon } from "@/images/icons/tasks-status.svg";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { Link } from "react-router-dom";

export function TaskStatus() {
  const branch = useAtomValue(currentBranchAtom);

  const { error, loading, data } = useQuery(TASKS_STATUS, {
    variables: { branch: branch?.name },
    pollInterval: 1000,
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
    <Link to={constructPath("/tasks", [{ name: QSP.FILTER, value: JSON.stringify([filter]) }])}>
      <ButtonWithTooltip
        size="square"
        variant="ghost"
        className="h-8 w-8 bg-neutral-50 border border-neutral-200 rounded-lg relative"
        tooltipEnabled
        tooltipContent={"Tasks"}
      >
        {loading && <Spinner />}

        {!loading && <TasksStatusIcon />}

        {!loading && count > 0 && <Pulse className="right-[6.5px] bottom-[6.5px]" />}
      </ButtonWithTooltip>
    </Link>
  );
}
