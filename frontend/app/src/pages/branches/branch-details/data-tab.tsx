import { useParams } from "react-router";

import { NodeDiff } from "@/entities/diff/ui/node-diff";

export function Component() {
  const { branchName } = useParams() as { branchName: string };
  return (
    <NodeDiff
      branch={branchName}
      filters={{
        namespace: { excludes: ["Schema"] },
        status: { excludes: ["UNCHANGED"] },
      }}
    />
  );
}
