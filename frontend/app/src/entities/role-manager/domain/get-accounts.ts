import {
  type GetAccountsFromApiParams,
  getAccountsFromApi,
} from "@/entities/role-manager/api/get-accounts-from-api";

export type GetAccountsParams = GetAccountsFromApiParams;

export async function getAccounts(params: GetAccountsParams) {
  const { data, errors } = await getAccountsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  return data;
}
