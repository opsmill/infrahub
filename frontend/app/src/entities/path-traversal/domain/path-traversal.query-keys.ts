type ContextParams = {
  branchName: string;
  atDate: Date | string | null;
};

type TraversalParams = ContextParams & {
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
    [...pathTraversalKeys.all, branchName, atDate] as const,
  traverse: (params: TraversalParams) =>
    [
      ...pathTraversalKeys.allWithContext(params),
      params.sourceId,
      params.destinationId,
      params.maxDepth,
      params.maxPaths,
      params.kindFilter,
      params.relationshipFilter,
      params.excludedKinds,
    ] as const,
};
