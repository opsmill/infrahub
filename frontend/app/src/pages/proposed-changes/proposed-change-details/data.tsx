import { NodeDiff } from "@/entities/diff/ui/node-diff";

export function Component() {
  return (
    <NodeDiff
      filters={{
        namespace: { excludes: ["Schema"] },
        status: { excludes: ["UNCHANGED"] },
      }}
    />
  );
}
