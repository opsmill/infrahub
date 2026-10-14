import {
  type GetRepositoryActivityFromApiParams,
  getRepositoryActivityFromApi,
} from "@/entities/repository/api/get-repository-activity-from-api";
import { mapRepositoryActivity } from "@/entities/repository/api/repository-activity.mappers";
import type { RepositoryActivity } from "@/entities/repository/domain/model/repository-activity";
import { toRepositoryActivityError } from "@/entities/repository/domain/rules/repository-activity-error";

export type GetRepositoryActivityParams = GetRepositoryActivityFromApiParams;

export type GetRepositoryActivityResult = RepositoryActivity;

export async function getRepositoryActivity(
  params: GetRepositoryActivityParams
): Promise<GetRepositoryActivityResult> {
  const { data } = await getRepositoryActivityFromApi(params).catch((error: unknown) => {
    throw toRepositoryActivityError(error);
  });

  return mapRepositoryActivity(data.InfrahubRepositoryActivity);
}
