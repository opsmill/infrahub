import { useParams } from "react-router";

import { ProposedChangeDetails } from "@/entities/proposed-changes/ui/proposed-change-details";
import { useGetProposedChangeDetails } from "@/entities/proposed-changes/ui/queries/get-proposed-change-details.query";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };
  const { data } = useGetProposedChangeDetails({ proposedChangeId });
  if (!data) return null;
  return <ProposedChangeDetails {...data} />;
}
