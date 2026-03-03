import type { components } from "@/shared/api/rest/types.generated";

export type ConfigAPI = components["schemas"]["ConfigAPI"];

export type SSOProvider = {
  name: string;
  displayLabel: string;
  icon: string;
  protocol: string;
  authorizePath: string;
  tokenPath: string;
};

export type Config = {
  installationType: string;
  allowAnonymousAccess: boolean;
  sso: {
    enabled: boolean;
    providers: SSOProvider[];
  };
};
