import { getAccountTokenFromApi } from "@/entities/user-profile/api/get-account-token-from-api";

export const getInfrahubAccountToken = async () => {
  const { data } = await getAccountTokenFromApi();

  return data?.InfrahubAccountToken?.edges?.map((edge) => edge.node) ?? [];
};
