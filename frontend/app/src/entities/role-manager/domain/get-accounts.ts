import type { Permission } from "@/entities/permission/types";
import { getPermission } from "@/entities/permission/utils";
import {
  type GetAccountsFromApiParams,
  getAccountsFromApi,
} from "@/entities/role-manager/api/get-accounts-from-api";

export type GetAccountsParams = GetAccountsFromApiParams;

export interface AccountGroupItem {
  id: string;
  display_label: string | null | undefined;
}

export interface AccountItem {
  id: string;
  display_label: string | null | undefined;
  hfid: string[] | null | undefined;
  name: string | null | undefined;
  description: string | null | undefined;
  accountType: string | null | undefined;
  status: {
    value: string | null | undefined;
    color: string | null | undefined;
    description: string | null | undefined;
  };
  memberOfGroups: AccountGroupItem[];
}

export interface AccountListResult {
  accounts: AccountItem[];
  count: number | undefined;
  permission: Permission;
}

export async function getAccounts(params: GetAccountsParams): Promise<AccountListResult> {
  const { data, errors } = await getAccountsFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  const root = data?.CoreGenericAccount;

  const permission = getPermission(root?.permissions?.edges);

  const accounts: AccountItem[] =
    root?.edges.map((edge) => ({
      id: edge?.node?.id ?? "",
      display_label: edge?.node?.display_label,
      hfid: edge?.node?.hfid,
      name: edge?.node?.name?.value,
      description: edge?.node?.description?.value,
      accountType: edge?.node?.account_type?.value,
      status: {
        value: edge?.node?.status?.value,
        color: edge?.node?.status?.color,
        description: edge?.node?.status?.description,
      },
      memberOfGroups:
        edge?.node?.member_of_groups?.edges?.map((groupEdge) => ({
          id: groupEdge?.node?.id ?? "",
          display_label: groupEdge?.node?.display_label,
        })) ?? [],
    })) ?? [];

  return {
    accounts,
    count: root?.count ?? undefined,
    permission,
  };
}
