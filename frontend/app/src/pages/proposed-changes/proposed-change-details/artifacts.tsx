import { ArtifactsDiff } from "@/entities/diff/ui/artifact-diff/artifacts-diff";
import { useProposedChangeOutlet } from "@/entities/proposed-changes/ui/use-proposed-change-outlet";

export function Component() {
  const { sourceBranch } = useProposedChangeOutlet();
  return <ArtifactsDiff branchName={sourceBranch} />;
}
