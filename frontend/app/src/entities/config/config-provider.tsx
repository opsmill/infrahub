import { getConfigQueryOptions } from "@/entities/config/get-config.query";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { useQuery } from "@tanstack/react-query";
import React from "react";

export const ConfigProvider = ({ children }: { children: React.ReactNode }) => {
  const { isPending, error } = useQuery(getConfigQueryOptions());

  if (isPending) {
    return <InfrahubLoading>Loading config...</InfrahubLoading>;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return children;
};
