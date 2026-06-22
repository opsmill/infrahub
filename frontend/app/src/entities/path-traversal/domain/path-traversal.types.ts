export type PathNode = {
  id: string;
  kind: string;
  label: string;
  display_label: string;
  hfid: string[];
};

export type PathRelationship = {
  from_rel: string;
  from_label: string;
  to_rel: string;
  to_label: string;
  kind: string;
};

export type PathHop = {
  node: PathNode;
  relationship: PathRelationship | null;
};

export type PathResult = {
  hops: PathHop[];
  depth: number;
};

export type PathTraversalResponse = {
  paths: PathResult[];
  source: PathNode;
  destination: PathNode;
  count: number;
};

export type ReachableNode = {
  node: PathNode;
  depth: number;
  path: PathResult;
};

export type ReachableNodesResponse = {
  source: PathNode;
  dependencies: ReachableNode[];
  count: number;
};

type ContextParams = {
  branchName?: string;
  atDate?: Date | string | null;
};

export type GetPathTraversalParams = ContextParams & {
  sourceId: string;
  destinationId: string;
  maxDepth?: number;
  maxPaths?: number;
  kindFilter?: string[];
  relationshipFilter?: string[];
  excludedKinds?: string[];
};

export type GetReachableNodesParams = ContextParams & {
  sourceId: string;
  targetKinds: string[];
  maxDepth?: number;
  maxResults?: number;
  maxPaths?: number;
  shortestPathsOnly?: boolean;
};
