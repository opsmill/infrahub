import { RelationshipNodeDisplay } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { NodeCore } from "@/entities/nodes/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { InputHTMLAttributes } from "react";

export interface ObjectInlineDisplayProps extends InputHTMLAttributes<HTMLDivElement> {
  node: NodeCore;
}

export function ObjectInlineDisplay({ node }: ObjectInlineDisplayProps) {
  const { schema } = useSchema(node.__typename);
  const schemaLabel = schema?.label ?? schema?.name ?? node.__typename;

  return (
    <div className="space-x-2">
      <span>{schemaLabel}</span>
      <RelationshipNodeDisplay node={node} />
    </div>
  );
}
