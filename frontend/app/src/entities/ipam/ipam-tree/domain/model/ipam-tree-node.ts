import type { NodeCore } from "@/entities/nodes/object/domain/model/node";

export interface IpamTreeNode extends NodeCore {
  descendants: {
    count: number;
  };
}
