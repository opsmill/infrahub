import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import type { StoredRange } from "@/entities/resource-manager/domain/model/number-pool-range";

export interface NumberPool extends NodeCore {
  schemaKind: string;
  attributeName: string;
}

export interface NumberPoolForEditing {
  id: string;
  name: string;
  description: string;
  node: string;
  nodeAttribute: string;
  allocationScope: string[];
  poolType: "User" | "Schema";
  ranges: StoredRange[];
}
