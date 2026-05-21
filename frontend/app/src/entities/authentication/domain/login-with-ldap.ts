import {
  type LoginWithLdapFromApiParams,
  loginWithLdapFromApi,
} from "@/entities/authentication/api/login-with-ldap-from-api";
import type { UserToken } from "@/entities/authentication/types";

export type LoginWithLdapParams = LoginWithLdapFromApiParams;

export type LoginWithLdap = (params: LoginWithLdapParams) => Promise<UserToken>;

export const loginWithLdap: LoginWithLdap = (params) => loginWithLdapFromApi(params);
