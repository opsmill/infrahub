import { useParams } from "react-router";

import { ArtifactsDiff } from "@/entities/diff/ui/artifact-diff/artifacts-diff";

export function Component() {
  const { branchName } = useParams() as { branchName: string };
  return <ArtifactsDiff branchName={branchName} />;
}
