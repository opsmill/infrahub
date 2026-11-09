import { getProposedChangeDetailsUrl } from "@/entities/proposed-changes/ui/routing/proposed-change-urls";
import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";

export interface OverviewTabProps {
  proposedChangeId: string;
}

export function OverviewTab({ proposedChangeId }: OverviewTabProps) {
  return <ProposedChangeTab to={getProposedChangeDetailsUrl(proposedChangeId)} label="Overview" />;
}
