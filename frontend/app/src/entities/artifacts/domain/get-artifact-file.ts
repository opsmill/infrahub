import {
  type GetArtifactFileFromApiParams,
  getArtifactFileFromApi,
} from "@/entities/artifacts/api/get-artifact-file-from-api";

export type GetArtifactFileParams = GetArtifactFileFromApiParams;
export type GetArtifactFile = (params: GetArtifactFileParams) => Promise<string>;

export const getArtifactFile: GetArtifactFile = async ({ storageId }: GetArtifactFileParams) => {
  const { data, error } = await getArtifactFileFromApi({ storageId });

  if (error) throw error;

  return data;
};
