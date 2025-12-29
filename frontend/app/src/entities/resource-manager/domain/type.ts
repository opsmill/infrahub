import type { NodeCore } from "@/entities/nodes/types";

export interface NumberPool extends NodeCore {
  schemaKind: string;
  attributeName: string;
}
