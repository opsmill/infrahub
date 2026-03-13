import {
  ToggleButton as AriaToggleButton,
  ToggleButtonGroup as AriaToggleButtonGroup,
  composeRenderProps,
  type ToggleButtonGroupProps,
  type ToggleButtonProps,
} from "react-aria-components";
import { Link, type LinkProps, useMatch } from "react-router";

import { classNames } from "@/shared/utils/common";

export const ToggleButtonGroup = ({ className, ...props }: ToggleButtonGroupProps) => (
  <AriaToggleButtonGroup
    className={composeRenderProps(className, (className) =>
      classNames("flex gap-1 rounded-md border border-gray-200 bg-gray-100 p-1 shadow-xs", className)
    )}
    {...props}
  />
);

export const ToggleButton = ({ className, ...props }: ToggleButtonProps) => (
  <AriaToggleButton
    className={composeRenderProps(className, (className, { isSelected }) =>
      classNames(
        "flex cursor-pointer items-center gap-1.5 rounded-sm px-3 py-1.5 font-medium text-sm outline-hidden transition-colors",
        "data-disabled:cursor-not-allowed data-disabled:opacity-50",
        isSelected
          ? "bg-white text-gray-900 shadow-xs"
          : "text-gray-500 hover:text-gray-700",
        className
      )
    )}
    {...props}
  />
);

const linkToggleButtonClass = (isActive: boolean, className?: string) =>
  classNames(
    "flex cursor-pointer items-center gap-1.5 rounded-sm px-3 py-1.5 font-medium text-sm outline-hidden transition-colors",
    isActive
      ? "bg-white text-gray-900 shadow-xs"
      : "text-gray-500 hover:text-gray-700",
    className
  );

interface LinkToggleButtonProps extends LinkProps {
  matchPath?: string;
}

export const LinkToggleButton = ({ className, to, matchPath, ...props }: LinkToggleButtonProps) => {
  const path = matchPath ?? (typeof to === "string" ? to : "");
  const match = useMatch(path);

  return (
    <Link
      to={to}
      className={linkToggleButtonClass(
        !!match,
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
    className={classNames("flex gap-1 rounded-md border border-gray-200 bg-gray-100 p-1 shadow-xs", className)}
  >
    {children}
  </div>
);
