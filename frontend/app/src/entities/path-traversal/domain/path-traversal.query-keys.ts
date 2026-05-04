type ContextParams = {
  branchName: string;
  atDate: Date | string | null;
};

export type TraversalParams = ContextParams & {
  sourceId: string;
  destinationId: string;
  maxDepth?: number;
  maxPaths?: number;
  kindFilter?: string[];
  relationshipFilter?: string[];
  excludedKinds?: string[];
};

export const pathTraversalKeys = {
  all: ["path-traversal"] as const,
  allWithContext: ({ branchName, atDate }: ContextParams) =>
    [...pathTraversalKeys.all, { branchName, atDate }] as const,
  traverse: (params: TraversalParams) => [...pathTraversalKeys.all, "traverse", params] as const,
};
