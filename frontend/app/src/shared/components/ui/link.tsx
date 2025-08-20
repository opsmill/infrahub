import { classNames } from "@/shared/utils/common";
import { LinkProps, NavLink, NavLinkProps, Link as RouterLink } from "react-router";

export const Link = (props: LinkProps) => {
  const { children, className, ...propsToPass } = props;

  return (
    <RouterLink
      {...propsToPass}
      className={classNames("cursor-pointer underline rounded-md", className)}
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
          "px-3 py-2 border-b-2 border-transparent inline-flex items-center gap-2 text-sm truncate h-11",
          isActive && "border-custom-blue-600"
        )
      }
      {...props}
    />
  );
}
