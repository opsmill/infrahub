import type React from "react";

import InfrahubLogoDark from "@/assets/Infrahub-SVG-hori-dark.svg?react";
import InfrahubLogoLight from "@/assets/Infrahub-SVG-hori-light.svg?react";

import { classNames } from "@/shared/utils/common";

interface InfrahubLogoProps extends React.ComponentPropsWithoutRef<"svg"> {}

export function InfrahubLogo({ className, ...props }: InfrahubLogoProps) {
  return (
    <>
      <InfrahubLogoLight {...props} className={classNames("dark:hidden", className)} />
      <InfrahubLogoDark {...props} className={classNames("hidden dark:block", className)} />
    </>
  );
}
