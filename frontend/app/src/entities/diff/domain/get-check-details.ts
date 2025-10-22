import {
  GetCheckDetailsFromApiParams,
  getCheckDetailsFromApi,
} from "@/entities/diff/api/get-check-details-from-api";

export const getCheckDetails = async ({ checkId }: GetCheckDetailsFromApiParams) => {
  const { data, error } = await getCheckDetailsFromApi({ checkId });

  if (error) throw error;

  return data?.CoreCheck?.edges?.[0]?.node ?? {};
};
