import {
  type CheckConnectivityFromApiParams,
  checkConnectivityFromApi,
} from "@/entities/repository/api/check-connectivity-from-api";

export type CheckConnectivityParams = CheckConnectivityFromApiParams;

export interface CheckConnectivityResult {
  ok: boolean;
  message?: string;
}

export type CheckConnectivity = (
  params: CheckConnectivityParams
) => Promise<CheckConnectivityResult>;

export const checkConnectivity: CheckConnectivity = async (params) => {
  const { data, errors } = await checkConnectivityFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  if (!data?.InfrahubRepositoryConnectivity) {
    throw new Error("Failed to check repository connectivity");
  }

  const result = data.InfrahubRepositoryConnectivity;

  return {
    ok: result.ok,
    message: result.message ?? undefined,
  };
};
