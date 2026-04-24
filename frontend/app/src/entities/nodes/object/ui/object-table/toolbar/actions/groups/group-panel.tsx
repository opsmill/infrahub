import { Card, CardHeader, type CardHeaderProps, type CardProps } from "@infrahub/ui/card";
import type React from "react";

import { classNames } from "@/shared/utils/common";

export function GroupCard({ className, ...props }: CardProps) {
  return (
    <Card
      className={classNames("max-h-[min(47rem,calc(100vh-6rem))] shadow-sm", className)}
      {...props}
    />
  );
}

export function GroupPanelHeader({ className, ...props }: CardHeaderProps) {
  return <CardHeader className={classNames("h-10 text-xs", className)} {...props} />;
}

export function GroupPanelBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={classNames("grow overflow-auto", className)} {...props} />;
}

export function GroupPanelFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={classNames("shrink-0 border-gray-200 border-t p-1 text-center", className)}
      {...props}
    />
  );
}
