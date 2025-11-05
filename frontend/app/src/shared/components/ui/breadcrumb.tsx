import { cva } from "class-variance-authority";
import type React from "react";
import { Button, type ButtonProps, Link, type LinkProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/style-rac";
import { Spinner } from "@/shared/components/ui/spinner";
import { classNames } from "@/shared/utils/common";

export function Breadcrumb({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={classNames("flex items-center text-sm", className)} {...props} />;
}

export function BreadcrumbSeparator({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="presentation"
      aria-hidden="true"
      className={classNames("select-none font-medium text-lg text-neutral-300", className)}
      {...props}
    >
      {children ?? "/"}
    </div>
  );
}
const breadcrumbItemStyle = cva(
  [
    focusVisibleStyle,
    "inline-flex items-center truncate rounded-lg border border-transparent px-2 py-0.5 text-stone-800",
  ],
  {
    variants: {
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
      <>
        <BreadcrumbSeparator />
        <Link
          className={(stylingProps) =>
            classNames(breadcrumbItemStyle(stylingProps), "hover:underline", className)
          }
          {...props}
        />
      </>
    );
  }

  return (
    <>
      <BreadcrumbSeparator />
      <Button
        className={(stylingProps) => classNames(breadcrumbItemStyle(stylingProps), className)}
        {...props}
      />
    </>
  );
}

export function BreadcrumbLoading() {
  return (
    <BreadcrumbItem isDisabled>
      <Spinner />
    </BreadcrumbItem>
  );
}

export function BreadcrumbError({ error }: { error: Error }) {
  console.error("IPAM Breadcrumb Error:", error);

  return (
    <BreadcrumbItem isDisabled className="text-red-500">
      Error loading breadcrumb
    </BreadcrumbItem>
  );
}
