import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface OverviewTabProps {
  proposedChangeId: string;
}

export function OverviewTab({ proposedChangeId }: OverviewTabProps) {
  return <ProposedChangeTab to={`/proposed-changes/${proposedChangeId}`} label="Overview" />;
}
