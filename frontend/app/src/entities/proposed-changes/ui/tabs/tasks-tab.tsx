import { TASK_TAB } from "@/shared/config/constants";

import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";
import { useGetTaskCount } from "@/entities/tasks/domain/get-node-task-count/get-task-count.query";

export interface TasksTabProps {
  proposedChangeId: string;
}

export function TasksTab({ proposedChangeId }: TasksTabProps) {
  const { isPending, data: count } = useGetTaskCount({ relatedNodeIds: [proposedChangeId] });

  return (
    <ProposedChangeTab tabId={TASK_TAB} label="Tasks" count={count} isCountLoading={isPending} />
  );
}
