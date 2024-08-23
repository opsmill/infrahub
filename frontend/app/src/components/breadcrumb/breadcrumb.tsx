import React from "react";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { Slot } from "@radix-ui/react-slot";
import { Link, LinkProps } from "react-router-dom";

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
    {...props}>
    {children ?? <Icon icon="mdi:slash-forward" className="text-xl text-gray-400 px-2" />}
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

export const BreadcrumbLink = React.forwardRef<
  HTMLAnchorElement,
  LinkProps & {
    asChild?: boolean;
  }
>(({ asChild, className, ...props }, ref) => {
  const Comp = asChild ? Slot : Link;

  return (
    <Comp
      ref={ref}
      className={classNames(
        "transition-colors cursor-pointer hover:underline hover:text-custom-blue-700",
        className
      )}
      {...props}
    />
  );
});
