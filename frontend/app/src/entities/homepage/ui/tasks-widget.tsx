import { Icon } from "@iconify-icon/react";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";

import { HomeCard } from "@/entities/homepage/ui/home-card";
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
    <HomeCard className={className}>
      <HomeCard.Title>
        <Row>
          <Icon icon={"mdi:shield-check"} /> Tasks overview
        </Row>

        <HomeCard.Link to={constructPath("/tasks")}>
          View all <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>

      <HomeCard.Content className="grid min-h-0 flex-1 grid-cols-1 gap-2 lg:grid-cols-5">
        <TaskHomepageColumn>
          <TaskHomepageColumnHeader variant={"green"}>COMPLETED</TaskHomepageColumnHeader>
          <TaskHomepageState
            states={[TASK_STATE_COMPLETED]}
            emptyTitle="No completed tasks"
            emptySubtitle="Finished tasks will appear here"
          />
        </TaskHomepageColumn>

        <TaskHomepageColumn>
          <TaskHomepageColumnHeader variant={"blue"}>RUNNING</TaskHomepageColumnHeader>
          <TaskHomepageState
            states={[TASK_STATE_RUNNING]}
            emptyTitle="All clear"
            emptySubtitle="No tasks are currently running"
          />
        </TaskHomepageColumn>

        <TaskHomepageColumn>
          <TaskHomepageColumnHeader variant={"yellow"}>PENDING</TaskHomepageColumnHeader>
          <TaskHomepageState
            states={[TASK_STATE_PENDING]}
            emptyTitle="Queue is empty"
            emptySubtitle="No tasks waiting to be processed"
          />
        </TaskHomepageColumn>

        <TaskHomepageColumn>
          <TaskHomepageColumnHeader variant={"red"}>FAILED</TaskHomepageColumnHeader>
          <TaskHomepageState
            states={[TASK_STATE_FAILED]}
            emptyTitle="No failures"
            emptySubtitle="All tasks completed successfully"
          />
        </TaskHomepageColumn>

        <TaskHomepageColumn>
          <TaskHomepageColumnHeader variant={"gray"}>MORE</TaskHomepageColumnHeader>
          <TaskHomepageState
            states={MORE_TASKS_STATES}
            emptyTitle="Nothing else"
            emptySubtitle="No other tasks to display"
          />
        </TaskHomepageColumn>
      </HomeCard.Content>
    </HomeCard>
  );
};
