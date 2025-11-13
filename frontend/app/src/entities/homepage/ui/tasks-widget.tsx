import { Icon } from "@iconify-icon/react";

import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/ui/badge";
import { HomeCard } from "@/shared/components/ui/home-card";
import { classNames } from "@/shared/utils/common";

import {
  MORE_TASKS_STATES,
  TASK_STATE_COMPLETED,
  TASK_STATE_FAILED,
  TASK_STATE_PENDING,
  TASK_STATE_RUNNING,
} from "@/entities/tasks/constants";
import { TaskHomepageState } from "@/entities/tasks/ui/task-homepage-state";

interface TasksWidgetProps {
  className?: string;
}

export const TasksWidget = ({ className }: TasksWidgetProps) => {
  return (
    <HomeCard className={classNames("flex flex-col", className)}>
      <HomeCard.Title className="flex items-center justify-between">
        <span className="flex items-center gap-2">
          <Icon icon={"mdi:shield-check"} /> Tasks overview
        </span>

        <HomeCard.Link to={constructPath("/tasks")}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>

      <HomeCard.Content className="">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          <TaskHomepageState states={[TASK_STATE_COMPLETED]}>
            <Badge variant={"green"}>COMPLETED</Badge>
          </TaskHomepageState>

          <TaskHomepageState states={[TASK_STATE_RUNNING]}>
            <Badge variant={"blue"}>RUNNING</Badge>
          </TaskHomepageState>

          <TaskHomepageState states={[TASK_STATE_PENDING]}>
            <Badge variant={"yellow"}>PENDING</Badge>
          </TaskHomepageState>

          <TaskHomepageState states={[TASK_STATE_FAILED]}>
            <Badge variant={"red"}>FAILED</Badge>
          </TaskHomepageState>

          <TaskHomepageState states={MORE_TASKS_STATES}>
            <Badge variant={"gray"}>MORE</Badge>
          </TaskHomepageState>
        </div>
      </HomeCard.Content>
    </HomeCard>
  );
};
