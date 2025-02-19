import { NodeCore } from "@/entities/nodes/types";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";

export function getNodeLabel({ node, schema }: { node: NodeCore; schema: IModelSchema }): string {
  if (schema.human_friendly_id && node.hfid) {
    return node.hfid.join(", ");
  }

  if (schema.display_labels && node.display_label) {
    return node.display_label;
  }

  return node.id;
}
