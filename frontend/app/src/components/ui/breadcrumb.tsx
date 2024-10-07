import React from "react";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";

export const Breadcrumb = React.forwardRef<HTMLOListElement, React.ComponentPropsWithoutRef<"ol">>(
  ({ className, ...props }, ref) => (
    <nav ref={ref} aria-label="breadcrumb">
      <ol
        ref={ref}
        className={classNames("flex items-center break-words text-sm", className)}
        {...props}
      />
    </nav>
  )
);

export const BreadcrumbSeparator = ({
  children,
  className,
  ...props
}: React.ComponentProps<"li">) => (
  <li
    role="presentation"
    aria-hidden="true"
    className={classNames("inline-flex", className)}
    {...props}
  >
    {children ?? <Icon icon="mdi:slash-forward" className="text-xl text-gray-400" />}
  </li>
);

export const BreadcrumbItem = React.forwardRef<HTMLLIElement, React.ComponentPropsWithoutRef<"li">>(
  ({ className, ...props }, ref) => (
    <li
      ref={ref}
      className={classNames("inline-flex items-center gap-1.5", className)}
      {...props}
    />
  )
);
