import type {
  GetPathTraversalParams,
  GetReachableNodesParams,
} from "@/entities/path-traversal/domain/model/path-traversal";

export const pathTraversalQueryKeys = {
  all: ["path-traversal"] as const,
  traverse: (params: GetPathTraversalParams) =>
    [...pathTraversalQueryKeys.all, "traverse", params] as const,
  reachable: (params: GetReachableNodesParams) =>
    [...pathTraversalQueryKeys.all, "reachable", params] as const,
} as const;
