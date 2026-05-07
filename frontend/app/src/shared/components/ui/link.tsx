import { useEffect, useRef } from "react";
import {
  type LinkProps,
  NavLink,
  type NavLinkProps,
  Link as RouterLink,
  useMatch,
} from "react-router";

import { classNames } from "@/shared/utils/common";

export const Link = (props: LinkProps) => {
  const { children, className, ...propsToPass } = props;

  return (
    <RouterLink
      {...propsToPass}
      className={classNames(
        "cursor-pointer rounded-md underline decoration-dotted hover:decoration-solid",
        className
      )}
    >
      {children}
    </RouterLink>
  );
};

interface LinkTabProps extends Omit<NavLinkProps, "to" | "className"> {
  to: string;
  className?: string;
  scrollIntoViewOnActive?: boolean;
}

export function LinkTab({ to, className, scrollIntoViewOnActive, ...props }: LinkTabProps) {
  const ref = useRef<HTMLAnchorElement>(null);
  const isActive = !!useMatch({ path: to, end: true });

  useEffect(() => {
    if (isActive && scrollIntoViewOnActive) {
      ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
    }
  }, [isActive, scrollIntoViewOnActive]);

  return (
    <NavLink
      ref={ref}
      to={to}
      end
      className={({ isActive }) =>
        classNames(
          "transition-all focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-custom-blue-600/25",
          "inline-flex h-11 scroll-m-10 items-center gap-2 truncate border-transparent border-b-2 px-3 py-2 font-medium text-sm",
          isActive
            ? "border-custom-blue-600 text-custom-blue-600"
            : "text-gray-500 hover:border-gray-300 hover:text-gray-700",
          className
        )
      }
      {...props}
    />
  );
}
