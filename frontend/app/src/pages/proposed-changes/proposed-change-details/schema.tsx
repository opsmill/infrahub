import { NodeDiff } from "@/entities/diff/ui/node-diff";

export function Component() {
  return (
    <NodeDiff
      filters={{
        namespace: { includes: ["Schema"], excludes: ["Profile"] },
        status: { excludes: ["UNCHANGED"] },
      }}
    />
  );
}
