import { useRequiredParams } from "@/shared/hooks/use-required-params";

import { ArtifactsDiff } from "@/entities/diff/ui/artifact-diff/artifacts-diff";

export function Component() {
  const { branchName } = useRequiredParams("branchName");
  return <ArtifactsDiff branchName={branchName} />;
}
