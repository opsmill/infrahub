import type React from "react";

import infrahubLogo from "@/assets/infrahub-logo.svg";

export const InfrahubLoading = ({ children }: { children?: React.ReactNode }) => {
  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center bg-background">
      <img src={infrahubLogo} alt="Infrahub logo" className="h-14 animate-bounce" />
      <span className="font-medium text-foreground">{children}</span>
    </div>
  );
};
