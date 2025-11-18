import { Slot } from "@radix-ui/react-slot";
import React from "react";
import { Link, type LinkProps } from "react-router";

import { breadcrumbItemStyle } from "@/shared/components/layout/breadcrumb-navigation/style";
import { classNames } from "@/shared/utils/common";

export const BreadcrumbLink = React.forwardRef<
  HTMLAnchorElement,
  LinkProps & {
    asChild?: boolean;
  }
>(({ asChild, className, ...props }, ref) => {
  const Comp = asChild ? Slot : Link;

  return <Comp ref={ref} className={classNames(breadcrumbItemStyle, className)} {...props} />;
});
