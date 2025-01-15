import infrahubLogo from "@/assets/infrahub-logo.svg";
import { getConfigQueryOptions } from "@/entities/config/get-config.query";
import { useQuery } from "@tanstack/react-query";
import React from "react";

export const ConfigProvider = ({ children }: { children: React.ReactNode }) => {
  const { isPending, error } = useQuery(getConfigQueryOptions());

  if (isPending) {
    return (
      <div className="h-screen w-screen bg-stone-100 flex items-center justify-center flex-col">
        <img src={infrahubLogo} alt="Infrahub logo" className="h-14 animate-bounce" />
        <span className="text-neutral-900 font-medium">Loading config...</span>
      </div>
    );
  }

  if (error) {
    return <div>Error: {error.message}</div>;
  }

  return children;
};
