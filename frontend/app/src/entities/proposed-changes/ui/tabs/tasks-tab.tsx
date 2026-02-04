import { TASK_TAB } from "@/shared/config/constants";

import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface TasksTabProps {
  tasksCount: number;
}

export function TasksTab({ tasksCount }: TasksTabProps) {
  return <ProposedChangeTab tabId={TASK_TAB} label="Tasks" count={tasksCount} />;
}
