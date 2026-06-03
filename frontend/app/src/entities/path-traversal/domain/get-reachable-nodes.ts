import { getReachableNodesFromApi } from "@/entities/path-traversal/api/get-reachable-nodes-from-api";
import type {
  GetReachableNodesParams,
  ReachableNodesResponse,
} from "@/entities/path-traversal/domain/path-traversal.types";

export async function getReachableNodes(
  params: GetReachableNodesParams
): Promise<ReachableNodesResponse> {
  const { data, errors } = await getReachableNodesFromApi(params);

  if (errors && errors.length > 0) {
    throw new Error(errors[0]?.message ?? "Unknown error");
  }

  return data.InfrahubReachableNodes;
}
