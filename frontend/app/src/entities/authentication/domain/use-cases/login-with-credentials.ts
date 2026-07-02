import {
  type LoginWithCredentialsFromApiParams,
  loginWithCredentialsFromApi,
} from "@/entities/authentication/api/login-with-credentials-from-api";
import type { UserToken } from "@/entities/authentication/types";

export type LoginWithCredentialsParams = LoginWithCredentialsFromApiParams;

export type LoginWithCredentials = (params: LoginWithCredentialsParams) => Promise<UserToken>;

export const loginWithCredentials: LoginWithCredentials = (params) =>
  loginWithCredentialsFromApi(params);
