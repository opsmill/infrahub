import type { GraphNode } from "@/entities/rack-elevation/domain/model/schema";

export type RackFace = "front" | "rear";

export interface WriteTarget {
  nodeId: string;
  attribute: string;
}

export interface ElevationItem {
  key: string;
  node: GraphNode;
  sourceId: string;
  sourceName: string;
  label: string;
  subtitle: string | null;
  position: number | null;
  height: number;
  face: RackFace;
  fullDepth: boolean;
  color: string;
  targets: {
    position: WriteTarget | null;
    face: WriteTarget | null;
    height: WriteTarget | null;
  };
}

export interface Elevation {
  rack: GraphNode;
  label: string;
  height: number;
  placed: ElevationItem[];
  unplaced: ElevationItem[];
  conflicts: Set<string>;
  issues: string[];
}
