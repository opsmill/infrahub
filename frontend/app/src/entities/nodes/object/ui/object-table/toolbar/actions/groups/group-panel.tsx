import { classNames } from "@/shared/utils/common";
import React from "react";

export function GroupPanelHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={classNames(
        "font-medium text-xs border-b border-gray-200 h-10 shrink-0 flex items-center p-2 text-neutral-600",
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
      className={classNames("shrink-0 p-1 text-center border-t border-gray-200", className)}
      {...props}
    />
  );
}
