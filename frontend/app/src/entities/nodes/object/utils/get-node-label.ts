import type { NodeCore } from "@/entities/nodes/types";
import { getSchema } from "@/entities/schema/domain/get-schema";

export function getNodeLabel(node: NodeCore): string {
  const { schema } = getSchema(node.__typename);

  if (!schema) return node.id;

  if (schema.human_friendly_id && node.hfid?.length) {
    return node.hfid.join(", ");
  }

  if ((schema.display_label || schema.display_labels) && node.display_label) {
    return node.display_label;
  }

  return node.id;
}
