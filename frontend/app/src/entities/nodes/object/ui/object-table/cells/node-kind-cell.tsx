import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { Badge } from "@/shared/components/ui/badge";
import { useAtomValue } from "jotai";

export function NodeKindCell({ kind }: { kind: string }) {
  const nodes = useAtomValue(nodeSchemasAtom);

  const currentNode = nodes.find((node) => {
    return node.kind === kind;
  });

  if (!kind || !currentNode) return "-";

  return (
    <div className="flex items-center gap-2">
      {currentNode?.label} <Badge>{currentNode?.namespace}</Badge>
    </div>
  );
}
