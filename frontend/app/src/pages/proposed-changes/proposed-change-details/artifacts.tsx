import { useParams } from "react-router";

import { ArtifactsDiff } from "@/entities/diff/ui/artifact-diff/artifacts-diff";
import { useGetProposedChangeDetails } from "@/entities/proposed-changes/ui/queries/get-proposed-change-details.query";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };
  const { data } = useGetProposedChangeDetails({ proposedChangeId });
  const branchName = data?.proposedChangeData.source_branch?.value;
  if (!branchName) return null;
  return <ArtifactsDiff branchName={branchName} />;
}
