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
import { TaskHomepageColumn } from "@/entities/tasks/ui/task-homepage-column";
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
          <TaskHomepageColumn>
            <Badge variant={"green"}>COMPLETED</Badge>
            <TaskHomepageState states={[TASK_STATE_COMPLETED]} />
          </TaskHomepageColumn>

          <TaskHomepageColumn>
            <Badge variant={"blue"}>RUNNING</Badge>
            <TaskHomepageState states={[TASK_STATE_RUNNING]} />
          </TaskHomepageColumn>

          <TaskHomepageColumn>
            <Badge variant={"yellow"}>PENDING</Badge>
            <TaskHomepageState states={[TASK_STATE_PENDING]} />
          </TaskHomepageColumn>

          <TaskHomepageColumn>
            <Badge variant={"red"}>FAILED</Badge>
            <TaskHomepageState states={[TASK_STATE_FAILED]} />
          </TaskHomepageColumn>

          <TaskHomepageColumn>
            <Badge variant={"gray"}>MORE</Badge>
            <TaskHomepageState states={MORE_TASKS_STATES} />
          </TaskHomepageColumn>
        </div>
      </HomeCard.Content>
    </HomeCard>
  );
};
