import type { NodeCore } from "@/entities/nodes/object/domain/model/node";

export interface NumberPool extends NodeCore {
  schemaKind: string;
  attributeName: string;
}
