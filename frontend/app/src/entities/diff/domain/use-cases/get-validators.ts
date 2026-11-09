import { getValidatorsFromApi } from "@/entities/diff/api/get-validators-from-api";

export type GetValidatorsParams = { proposedChangeId: string };

export const getValidators = async ({ proposedChangeId }: GetValidatorsParams) => {
  const { data, error } = await getValidatorsFromApi({ id: proposedChangeId });

  if (error) throw error;

  return data.CoreValidator.edges.map((edge) => edge.node).filter((node) => !!node);
};
