import { ProposedChangeTab } from "@/entities/proposed-changes/ui/tabs/proposed-change-tab";
import { getProposedChangeDetailsUrl } from "@/entities/proposed-changes/utils";

export interface OverviewTabProps {
  proposedChangeId: string;
}

export function OverviewTab({ proposedChangeId }: OverviewTabProps) {
  return <ProposedChangeTab to={getProposedChangeDetailsUrl(proposedChangeId)} label="Overview" />;
}
