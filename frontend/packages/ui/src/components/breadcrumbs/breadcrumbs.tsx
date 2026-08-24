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
import { cn, tv } from "tailwind-variants";

import { focusVisibleStyle } from "../../styles/focus-visible";
import { composeAriaClassName } from "../../utils/compose-aria-class-name";
import { Spinner } from "../spinner/spinner";

export interface BreadcrumbsProps<T extends object> extends AriaBreadcrumbsProps<T> {}

export function Breadcrumbs<T extends object>({ className, ...props }: BreadcrumbsProps<T>) {
  return <AriaBreadcrumbs className={cn("flex items-center text-sm", className)} {...props} />;
}

export interface BreadcrumbProps extends AriaBreadcrumbProps {}

export function Breadcrumb({ children, className, ...props }: BreadcrumbProps) {
  return (
    <AriaBreadcrumb className={cn("inline-flex items-center", className)} {...props}>
      {composeRenderProps(children, (resolvedChildren) => (
        <>
          <span
            role="presentation"
            aria-hidden="true"
            className="select-none font-medium text-border-strong text-lg"
          >
            /
          </span>
          {resolvedChildren}
        </>
      ))}
    </AriaBreadcrumb>
  );
}

const breadcrumbItemVariants = tv({
  base: [
    focusVisibleStyle,
    "inline-flex items-center truncate rounded-lg border border-transparent px-2 py-0.5 text-foreground",
  ],
  variants: {
    isPressed: {
      true: "bg-highlight",
    },
  },
});

export type BreadcrumbItemProps =
  | AriaButtonProps
  | (AriaLinkProps & { href: AriaLinkProps["href"] });

export function BreadcrumbItem(props: BreadcrumbItemProps) {
  if ("href" in props) {
    const { className, ...rest } = props;
    return (
      <Breadcrumb>
        <AriaLink
          className={composeAriaClassName(className, ({ isPressed }) =>
            cn(breadcrumbItemVariants({ isPressed }), "hover:underline")
          )}
          {...rest}
        />
      </Breadcrumb>
    );
  }

  const { className, ...rest } = props;
  return (
    <Breadcrumb>
      <AriaButton
        className={composeAriaClassName(className, ({ isPressed }) =>
          breadcrumbItemVariants({ isPressed })
        )}
        {...rest}
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
