import { useBranchDetailsOutlet } from "@/entities/branches/ui/routing/use-branch-details-outlet";
import { ArtifactsDiff } from "@/entities/diff/ui/artifact-diff/artifacts-diff";

export function Component() {
  const { branch } = useBranchDetailsOutlet();
  return <ArtifactsDiff branchName={branch.name} />;
}
