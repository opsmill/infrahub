import { getReachableObjectsFromApi } from "@/entities/path-traversal/api/get-reachable-objects-from-api";
import type {
  GetReachableObjectsParams,
  ReachableObjectsResponse,
} from "@/entities/path-traversal/domain/path-traversal.types";

export async function getReachableObjects(
  params: GetReachableObjectsParams
): Promise<ReachableObjectsResponse> {
  const { data, errors } = await getReachableObjectsFromApi(params);

  if (errors && errors.length > 0) {
    throw new Error(errors[0]?.message ?? "Unknown error");
  }

  return data.InfrahubReachableNodes;
}
