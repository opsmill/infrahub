import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

export function getNodeLabel(node: NodeCore): string {
  const { schema } = getSchema(node.__typename);

  if (!schema) return node.id;

  if ((schema.display_label || schema.display_labels) && node.display_label) {
    return node.display_label;
  }

  if (schema.human_friendly_id && node.hfid?.length) {
    return node.hfid.join(", ");
  }

  return node.id;
}
