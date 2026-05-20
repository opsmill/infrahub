import {
  type GetValidatorDetailsFromApiParams,
  getValidatorDetailsFromApi,
} from "@/entities/diff/api/get-validator-details-from-api";

export type GetValidatorDetailsParams = GetValidatorDetailsFromApiParams;

export async function getValidatorDetails(params: GetValidatorDetailsParams) {
  const { data, error } = await getValidatorDetailsFromApi(params);

  if (error) throw error;

  return data?.CoreValidator?.edges?.[0]?.node ?? null;
}
