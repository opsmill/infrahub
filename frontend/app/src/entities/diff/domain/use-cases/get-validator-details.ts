import { getArtifactValidatorDetailsFromApi } from "@/entities/diff/api/get-artifact-validator-details-from-api";
import {
  type GetValidatorDetailsFromApiParams,
  getValidatorDetailsFromApi,
} from "@/entities/diff/api/get-validator-details-from-api";

export type GetValidatorDetailsParams = GetValidatorDetailsFromApiParams & {
  checksFailedFirst?: boolean;
};

export async function getValidatorDetails({
  checksFailedFirst,
  ...params
}: GetValidatorDetailsParams) {
  if (checksFailedFirst !== undefined) {
    const { data, errors } = await getArtifactValidatorDetailsFromApi({
      ...params,
      checksFailedFirst,
    });

    if (errors?.length) {
      throw new Error(errors.map((error) => error.message).join("; "));
    }

    return data?.CoreArtifactValidator?.edges?.[0]?.node ?? null;
  }

  const { data, errors } = await getValidatorDetailsFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  return data?.CoreValidator?.edges?.[0]?.node ?? null;
}
