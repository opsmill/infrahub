import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";
import { getProposedChangeDetailsUrl } from "@/entities/proposed-changes/utils";
import { useGetTaskCount } from "@/entities/tasks/ui/queries/get-task-count.query";

export interface TasksTabProps {
  proposedChangeId: string;
}

export function TasksTab({ proposedChangeId }: TasksTabProps) {
  const { isPending, data: count } = useGetTaskCount({ relatedNodeIds: [proposedChangeId] });

  return (
    <ProposedChangeTab
      to={getProposedChangeDetailsUrl(proposedChangeId, "tasks")}
      label="Tasks"
      count={count}
      isCountLoading={isPending}
    />
  );
}
