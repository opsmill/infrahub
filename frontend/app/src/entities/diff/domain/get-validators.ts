import {
  GetValidatorsFromApiParams,
  getValidatorsFromApi,
} from "@/entities/diff/api/get-validators-from-api";

export const getValidators = async ({ proposedChangeId }: GetValidatorsFromApiParams) => {
  const { data } = await getValidatorsFromApi({ proposedChangeId });

  return data?.CoreValidator?.edges?.map((edge: any) => edge.node) ?? [];
};
