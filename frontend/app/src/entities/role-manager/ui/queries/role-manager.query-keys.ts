import type { PaginationParams } from "@/shared/api/types";

export interface RoleManagerSearchParams extends PaginationParams {
  search?: string;
  branchName: string;
  atDate?: Date | null;
}

export const roleManagerQueryKeys = {
  all: ["role-manager"] as const,
  counts: (params: { branchName: string; atDate?: Date | null }) =>
    [...roleManagerQueryKeys.all, "counts", params.branchName, params.atDate] as const,
  accounts: (params: RoleManagerSearchParams) =>
    [
      ...roleManagerQueryKeys.all,
      "accounts",
      params.search,
      params.offset,
      params.limit,
      params.branchName,
      params.atDate,
    ] as const,
  groups: (params: RoleManagerSearchParams) =>
    [
      ...roleManagerQueryKeys.all,
      "groups",
      params.search,
      params.offset,
      params.limit,
      params.branchName,
      params.atDate,
    ] as const,
  roles: (params: RoleManagerSearchParams) =>
    [
      ...roleManagerQueryKeys.all,
      "roles",
      params.search,
      params.offset,
      params.limit,
      params.branchName,
      params.atDate,
    ] as const,
  globalPermissions: (params: RoleManagerSearchParams) =>
    [
      ...roleManagerQueryKeys.all,
      "global-permissions",
      params.search,
      params.offset,
      params.limit,
      params.branchName,
      params.atDate,
    ] as const,
  objectPermissions: (params: RoleManagerSearchParams) =>
    [
      ...roleManagerQueryKeys.all,
      "object-permissions",
      params.search,
      params.offset,
      params.limit,
      params.branchName,
      params.atDate,
    ] as const,
};
