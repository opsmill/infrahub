import React from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";

import type { Config } from "@/entities/config/types";
import { useGetConfig } from "@/entities/config/ui/queries/get-config.query";

export const ConfigContext = React.createContext<Config>({} as Config);

export function useConfig() {
  const context = React.use(ConfigContext);

  if (!context) {
    throw new Error("useConfig must be used within a ConfigContext.");
  }

  return context;
}

export const ConfigProvider = ({ children }: { children: React.ReactNode }) => {
  const { isPending, error, data } = useGetConfig();

  if (isPending) {
    return <InfrahubLoading>Loading config...</InfrahubLoading>;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return <ConfigContext value={data}>{children}</ConfigContext>;
};
