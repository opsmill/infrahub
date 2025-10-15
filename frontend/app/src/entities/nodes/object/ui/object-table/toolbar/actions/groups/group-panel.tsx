import type React from "react";

import { Card, type CardProps } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";

export function GroupCard({ className, ...props }: CardProps) {
  return (
    <Card
      className={classNames(
        "flex max-h-[min(47rem,calc(100vh-6rem))] flex-col overflow-hidden p-0 shadow-sm",
        className
      )}
      {...props}
    />
  );
}

export function GroupPanelHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={classNames(
        "flex h-10 shrink-0 items-center border-gray-200 border-b p-2 font-medium text-neutral-600 text-xs",
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
  return (
    <div
      className={classNames("shrink-0 border-gray-200 border-t p-1 text-center", className)}
      {...props}
    />
  );
}
