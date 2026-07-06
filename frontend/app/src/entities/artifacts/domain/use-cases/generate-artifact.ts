import {
  type GenerateArtifactFromApiParams,
  generateArtifactFromApi,
} from "@/entities/artifacts/api/generate-artifact-from-api";

export type GenerateArtifactParams = GenerateArtifactFromApiParams;

export type GenerateArtifact = (params: GenerateArtifactParams) => Promise<void>;

export const generateArtifact: GenerateArtifact = async (params) => {
  const { error } = await generateArtifactFromApi(params);

  if (error) throw error;
};
