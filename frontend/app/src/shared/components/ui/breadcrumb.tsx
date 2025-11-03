import { Icon } from "@iconify-icon/react";
import { cva } from "class-variance-authority";
import type React from "react";
import { Button, type ButtonProps, Link, type LinkProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/style-rac";
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
const breadcrumbItemStyle = cva(
  [
    focusVisibleStyle,
    "inline-flex items-center truncate rounded-lg border border-transparent px-2 py-1 text-stone-800",
  ],
  {
    variants: {
      isHovered: {
        true: "bg-stone-100",
      },
      isPressed: {
        true: "bg-stone-100",
      },
    },
  }
);

type BreadcrumbItemProps = ButtonProps | (LinkProps & { href: LinkProps["href"] });

export function BreadcrumbItem({ className, ...props }: BreadcrumbItemProps) {
  if ("href" in props) {
    return (
      <Link
        className={(stylingProps) => classNames(breadcrumbItemStyle(stylingProps), className)}
        {...props}
      />
    );
  }

  return (
    <Button
      className={(stylingProps) => classNames(breadcrumbItemStyle(stylingProps), className)}
      {...props}
    />
  );
}
