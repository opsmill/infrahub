import { getAccountTokenFromApi } from "@/entities/user-profile/api/get-account-token-from-api";
import { AccountTokenEdge, AccountTokenNode } from "@/shared/api/graphql/generated/graphql";

export type GetInfrahubAccountToken = () => Array<AccountTokenNode>;

export const getInfrahubAccountToken: GetInfrahubAccountToken = async () => {
  const { data } = await getAccountTokenFromApi();

  return data?.InfrahubAccountToken?.edges?.map((edge: AccountTokenEdge) => edge.node) ?? [];
};
