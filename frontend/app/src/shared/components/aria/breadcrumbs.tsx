import { cva } from "class-variance-authority";
import {
  Breadcrumb as AriaBreadcrumb,
  type BreadcrumbProps as AriaBreadcrumbProps,
  Breadcrumbs as AriaBreadcrumbs,
  type BreadcrumbsProps as AriaBreadcrumbsProps,
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
  Link as AriaLink,
  type LinkProps as AriaLinkProps,
  composeRenderProps,
} from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { Spinner } from "@/shared/components/ui/spinner";
import { classNames } from "@/shared/utils/common";

export function Breadcrumbs<T extends object>({ className, ...props }: AriaBreadcrumbsProps<T>) {
  return (
    <AriaBreadcrumbs className={classNames("flex items-center text-sm", className)} {...props} />
  );
}

export function Breadcrumb({ children, className, ...props }: AriaBreadcrumbProps) {
  return (
    <AriaBreadcrumb className={classNames("inline-flex items-center", className)} {...props}>
      {composeRenderProps(children, (children) => (
        <>
          <span
            role="presentation"
            aria-hidden="true"
            className="select-none font-medium text-lg text-neutral-300"
          >
            /
          </span>
          {children}
        </>
      ))}
    </AriaBreadcrumb>
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

type BreadcrumbItemProps = AriaButtonProps | (AriaLinkProps & { href: AriaLinkProps["href"] });

export function BreadcrumbItem({ className, ...props }: BreadcrumbItemProps) {
  if ("href" in props) {
    return (
      <Breadcrumb>
        <AriaLink
          className={(stylingProps) =>
            classNames(breadcrumbItemStyle(stylingProps), "hover:underline", className)
          }
          {...props}
        />
      </Breadcrumb>
    );
  }

  return (
    <Breadcrumb>
      <AriaButton
        className={(stylingProps) => classNames(breadcrumbItemStyle(stylingProps), className)}
        {...props}
      />
    </Breadcrumb>
  );
}

export function BreadcrumbItemLoading() {
  return (
    <BreadcrumbItem isDisabled>
      <Spinner />
    </BreadcrumbItem>
  );
}

export function BreadcrumbItemError({ error }: { error: Error }) {
  console.error("Breadcrumb Error:", error);

  return (
    <BreadcrumbItem isDisabled className="text-red-500">
      Error loading breadcrumb
    </BreadcrumbItem>
  );
}
