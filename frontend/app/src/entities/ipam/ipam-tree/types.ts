import type { NodeCore } from "@/entities/nodes/types";

export interface IpamTreeNode extends NodeCore {
  descendants: {
    count: number;
  };
}
