import { getCheckDetailsFromApi } from "@/entities/diff/api/get-check-details-from-api";

export type GetCheckDetailsParams = { checkId: string };

export const getCheckDetails = async ({ checkId }: GetCheckDetailsParams) => {
  const { data, error } = await getCheckDetailsFromApi({ id: checkId });

  if (error) throw error;

  return data?.CoreCheck?.edges?.[0]?.node ?? null;
};
