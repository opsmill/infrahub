import { Icon } from "@iconify-icon/react";

import { constructPath } from "@/shared/api/rest/fetch";
import { HomeCard } from "@/shared/components/ui/home-card";
import { classNames } from "@/shared/utils/common";

import {
  MORE_TASKS_STATES,
  TASK_STATE_COMPLETED,
  TASK_STATE_FAILED,
  TASK_STATE_PENDING,
  TASK_STATE_RUNNING,
} from "@/entities/tasks/constants";
import {
  TaskHomepageColumn,
  TaskHomepageColumnHeader,
} from "@/entities/tasks/ui/tasks-homepage/task-homepage-column";
import { TaskHomepageState } from "@/entities/tasks/ui/tasks-homepage/task-homepage-state";

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

      <HomeCard.Content className="grid grid-cols-1 gap-2 lg:grid-cols-5">
        <TaskHomepageColumn>
          <TaskHomepageColumnHeader variant={"green"}>COMPLETED</TaskHomepageColumnHeader>
          <TaskHomepageState states={[TASK_STATE_COMPLETED]} />
        </TaskHomepageColumn>

        <TaskHomepageColumn>
          <TaskHomepageColumnHeader variant={"blue"}>RUNNING</TaskHomepageColumnHeader>
          <TaskHomepageState states={[TASK_STATE_RUNNING]} />
        </TaskHomepageColumn>

        <TaskHomepageColumn>
          <TaskHomepageColumnHeader variant={"yellow"}>PENDING</TaskHomepageColumnHeader>
          <TaskHomepageState states={[TASK_STATE_PENDING]} />
        </TaskHomepageColumn>

        <TaskHomepageColumn>
          <TaskHomepageColumnHeader variant={"red"}>FAILED</TaskHomepageColumnHeader>
          <TaskHomepageState states={[TASK_STATE_FAILED]} />
        </TaskHomepageColumn>

        <TaskHomepageColumn>
          <TaskHomepageColumnHeader variant={"gray"}>MORE</TaskHomepageColumnHeader>
          <TaskHomepageState states={MORE_TASKS_STATES} />
        </TaskHomepageColumn>
      </HomeCard.Content>
    </HomeCard>
  );
};
