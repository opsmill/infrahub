import { Card, type CardProps } from "@infrahub/ui";
import type React from "react";

import { classNames } from "@/shared/utils/common";

export function GroupCard({ className, ...props }: CardProps) {
  return (
    // biome-ignore lint/nursery/noTailwindArbitraryValue: calc: clamps a panel to the smaller of a fixed max and the viewport; no single token expresses it
    <Card className={classNames("max-h-[min(47rem,calc(100vh-6rem))]", className)} {...props} />
  );
}

export function GroupPanelHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={classNames(
        "flex h-10 shrink-0 items-center border-b p-2 font-medium text-foreground-muted text-xs",
        className
      )}
      {...props}
    />
  );
}

export function GroupPanelBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={classNames("grow overflow-auto", className)} {...props} />;
}

export function GroupPanelFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={classNames("shrink-0 border-t p-1 text-center", className)} {...props} />;
}
