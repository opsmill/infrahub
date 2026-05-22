import {
  type GetValidatorDetailsFromApiParams,
  getValidatorDetailsFromApi,
} from "@/entities/diff/api/get-validator-details-from-api";

export type GetValidatorDetailsParams = GetValidatorDetailsFromApiParams;

export async function getValidatorDetails(params: GetValidatorDetailsParams) {
  const { data, errors } = await getValidatorDetailsFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data?.CoreValidator?.edges?.[0]?.node ?? null;
}
