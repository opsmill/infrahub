import {
  type CreateAccountTokenFromApiParams,
  createAccountTokenFromApi,
} from "@/entities/user-profile/api/create-account-token-from-api";

export type CreateAccountTokenParams = CreateAccountTokenFromApiParams;

export type CreateAccountToken = (params: CreateAccountTokenParams) => Promise<{ token: string }>;

export const createAccountToken: CreateAccountToken = async (params) => {
  const { data, errors } = await createAccountTokenFromApi(params);

  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  const token = data?.InfrahubAccountTokenCreate?.object?.token?.value;
  if (!token) {
    throw new Error("Failed to create account token");
  }

  return { token };
};
