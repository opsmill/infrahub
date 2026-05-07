import { useRequiredParams } from "@/shared/hooks/use-required-params";

import { NodeDiff } from "@/entities/diff/ui/node-diff";

export function Component() {
  const { branchName } = useRequiredParams("branchName");
  return (
    <NodeDiff
      branch={branchName}
      filters={{
        namespace: { includes: ["Schema"], excludes: ["Profile"] },
        status: { excludes: ["UNCHANGED"] },
      }}
    />
  );
}
