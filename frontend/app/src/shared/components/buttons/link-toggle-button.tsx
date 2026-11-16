import { Link, type LinkProps, useMatch } from "react-router";

import { classNames } from "@/shared/utils/common";

interface LinkToggleButtonProps extends LinkProps {
  matchPath?: string;
}

export const LinkToggleButton = ({ className, to, matchPath, ...props }: LinkToggleButtonProps) => {
  const path = matchPath ?? (typeof to === "string" ? to : "");
  const match = useMatch(path);
  const isActive = !!match;

  return (
    <Link
      to={to}
      className={classNames(
        "flex cursor-pointer items-center gap-1.5 rounded-sm px-3 py-1.5 font-medium text-sm outline-hidden transition-colors",
        isActive
          ? "bg-selected text-foreground shadow-xs"
          : "text-foreground-muted hover:text-foreground",
        typeof className === "string" ? className : undefined
      )}
      {...props}
    />
  );
};

interface LinkToggleButtonGroupProps {
  className?: string;
  children: React.ReactNode;
}

export const LinkToggleButtonGroup = ({ className, children }: LinkToggleButtonGroupProps) => (
  <div
    className={classNames("flex gap-1 rounded-md border bg-background p-1 shadow-xs", className)}
  >
    {children}
  </div>
);
