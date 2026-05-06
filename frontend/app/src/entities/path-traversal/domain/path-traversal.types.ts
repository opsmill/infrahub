export type PathObject = {
  id: string;
  kind: string;
  display_label: string;
};

export type PathRelationship = {
  id: string;
  name: string;
  direction: "OUTBOUND" | "INBOUND";
};

export type PathResult = {
  objects: PathObject[];
  relationships: PathRelationship[];
  depth: number;
};

export type PathTraversalResponse = {
  paths: PathResult[];
  source: PathObject;
  destination: PathObject;
  total_paths_found: number;
};

export type ReachableObject = {
  id: string;
  kind: string;
  display_label: string;
  depth: number;
  relationship_name: string;
  path: PathResult;
};

export type ReachableObjectsResponse = {
  source: PathObject;
  reachable_objects: ReachableObject[];
  paths: PathResult[];
  total_found: number;
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

export type GetReachableObjectsParams = ContextParams & {
  sourceId: string;
  targetKinds: string[];
  maxDepth?: number;
  maxResults?: number;
};
