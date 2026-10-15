import {
  type GetRepositoryActivityFromApiParams,
  getRepositoryActivityFromApi,
} from "@/entities/repository/api/get-repository-activity-from-api";
import { mapRepositoryActivity } from "@/entities/repository/api/repository-activity.mappers";
import type { RepositoryActivity } from "@/entities/repository/domain/model/repository-activity";

export type GetRepositoryActivityParams = GetRepositoryActivityFromApiParams;

export type GetRepositoryActivityResult = RepositoryActivity;

export async function getRepositoryActivity(
  params: GetRepositoryActivityParams
): Promise<GetRepositoryActivityResult> {
  const { data } = await getRepositoryActivityFromApi(params);

  return mapRepositoryActivity(data.InfrahubRepositoryActivity);
}
