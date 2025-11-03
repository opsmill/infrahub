import { Icon } from "@iconify-icon/react";
import React from "react";

import { classNames } from "@/shared/utils/common";

export function Breadcrumb({ className, ...props }: React.OlHTMLAttributes<HTMLOListElement>) {
  return <ol className={classNames("flex items-center text-sm", className)} {...props} />;
}

export function BreadcrumbSeparator({
  children,
  className,
  ...props
}: React.LiHTMLAttributes<HTMLLIElement>) {
  return (
    <li
      role="presentation"
      aria-hidden="true"
      className={classNames("inline-flex", className)}
      {...props}
    >
      {children ?? <Icon icon="mdi:slash-forward" className="text-gray-400 text-xl" />}
    </li>
  );
}

export const BreadcrumbItem = React.forwardRef<HTMLLIElement, React.ComponentPropsWithoutRef<"li">>(
  ({ className, ...props }, ref) => (
    <li
      ref={ref}
      className={classNames("inline-flex items-center gap-1.5", className)}
      {...props}
    />
  )
);
