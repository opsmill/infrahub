import {
  GetValidatorsFromApiParams,
  getValidatorsFromApi,
} from "@/entities/diff/api/get-validators-from-api";

export const getValidators = async ({ proposedChangeId }: GetValidatorsFromApiParams) => {
  const { data, error } = await getValidatorsFromApi({ proposedChangeId });

  if (error) throw error;

  return data?.CoreValidator?.edges?.map((edge: any) => edge.node) ?? [];
};
