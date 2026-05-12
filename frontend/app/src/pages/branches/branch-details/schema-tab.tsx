import { useBranchDetailsOutlet } from "@/entities/branches/ui/use-branch-details-outlet";
import { NodeDiff } from "@/entities/diff/ui/node-diff";

export function Component() {
  const { branch } = useBranchDetailsOutlet();
  return (
    <NodeDiff
      branch={branch.name}
      filters={{
        namespace: { includes: ["Schema"], excludes: ["Profile"] },
        status: { excludes: ["UNCHANGED"] },
      }}
    />
  );
}
