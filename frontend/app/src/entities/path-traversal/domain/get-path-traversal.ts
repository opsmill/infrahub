import { getPathTraversalFromApi } from "@/entities/path-traversal/api/get-path-traversal-from-api";
import type {
  GetPathTraversalParams,
  PathTraversalResponse,
} from "@/entities/path-traversal/domain/path-traversal.types";

export async function getPathTraversal(
  params: GetPathTraversalParams
): Promise<PathTraversalResponse> {
  const { data, errors } = await getPathTraversalFromApi(params);

  if (errors && errors.length > 0) {
    throw new Error(errors[0]?.message ?? "Unknown error");
  }

  return data.InfrahubPathTraversal;
}
