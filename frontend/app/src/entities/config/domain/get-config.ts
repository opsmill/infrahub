import { apiClient } from "@/shared/api/rest/client";

import type { Config } from "@/entities/config/types";

export type GetConfig = () => Promise<Config>;

export const getConfig: GetConfig = async () => {
  const { data, error } = await apiClient.GET("/api/config");

  if (error) throw error;

  return {
    installationType: data.installation_type,
    allowAnonymousAccess: data.main.allow_anonymous_access,
    sso: {
      enabled: data.sso.enabled,
      providers: (data.sso.providers ?? []).map((p) => ({
        name: p.name,
        displayLabel: p.display_label,
        icon: p.icon,
        protocol: p.protocol,
        authorizePath: p.authorize_path,
        tokenPath: p.token_path,
      })),
    },
  };
};
