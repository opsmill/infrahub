import {
  type CheckArtifactEncryptionFromApiParams,
  checkArtifactEncryptionFromApi,
} from "@/entities/artifacts/api/check-artifact-encryption-from-api";

export type CheckArtifactEncryptionParams = CheckArtifactEncryptionFromApiParams;

export const checkArtifactEncryption = async (params: CheckArtifactEncryptionParams) => {
  const { data, error } = await checkArtifactEncryptionFromApi(params);

  if (error) throw error;

  return data;
};
