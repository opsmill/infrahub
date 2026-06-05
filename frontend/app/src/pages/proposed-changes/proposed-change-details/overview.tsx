import { ProposedChangeDetails } from "@/entities/proposed-changes/ui/proposed-change-details";
import { useProposedChangeOutlet } from "@/entities/proposed-changes/ui/use-proposed-change-outlet";

export function Component() {
  const { proposedChangeData, metadata } = useProposedChangeOutlet();
  return <ProposedChangeDetails proposedChangeData={proposedChangeData} metadata={metadata} />;
}
