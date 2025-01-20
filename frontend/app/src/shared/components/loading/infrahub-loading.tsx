import infrahubLogo from "@/assets/infrahub-logo.svg";
import React from "react";

export const InfrahubLoading = ({ children }: { children?: React.ReactNode }) => {
  return (
    <div className="h-screen w-screen bg-stone-100 flex items-center justify-center flex-col">
      <img src={infrahubLogo} alt="Infrahub logo" className="h-14 animate-bounce" />
      <span className="text-neutral-900 font-medium">{children}</span>
    </div>
  );
};
