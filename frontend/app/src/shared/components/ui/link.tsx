import { type LinkProps, NavLink, type NavLinkProps, Link as RouterLink } from "react-router";

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

interface LinkTabProps extends Omit<NavLinkProps, "to"> {
  href: string;
}

export function LinkTab({ href, className, ...props }: LinkTabProps) {
  return (
    <NavLink
      to={href}
      end
      className={({ isActive }) =>
        classNames(
          "transition-all focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-custom-blue-600/25",
          "inline-flex h-11 items-center gap-2 truncate border-transparent border-b-2 px-3 py-2 text-sm",
          isActive && "border-custom-blue-600"
        )
      }
      {...props}
    />
  );
}
