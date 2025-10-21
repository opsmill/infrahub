import {
  GetCheckDetailsFromApiParams,
  getCheckDetailsFromApi,
} from "@/entities/diff/api/get-check-details-from-api";

export const getCheckDetails = async ({ checkId }: GetCheckDetailsFromApiParams) => {
  const { data } = await getCheckDetailsFromApi({ checkId });

  return data?.CoreCheck?.edges?.[0]?.node ?? {};
};
