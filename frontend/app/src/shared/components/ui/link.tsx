import { classNames } from "@/shared/utils/common";
import { LinkProps, Link as RouterLink } from "react-router";

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

interface LinkTabProps extends Omit<LinkProps, "to"> {
  href: string;
}

export function LinkTab({ href, className, ...props }: LinkTabProps) {
  const isTabActive = location.pathname.endsWith(href.split("?")?.[0] as string);

  return (
    <RouterLink
      to={href}
      className={classNames(
        "transition-all px-3 py-2 border-b-2 border-transparent inline-flex items-center gap-2 text-sm truncate h-10",
        isTabActive && "border-custom-blue-600"
      )}
      {...props}
    />
  );
}
