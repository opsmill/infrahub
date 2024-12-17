import { classNames } from "@/utils/common";
import { LinkProps, Link as RouterLink } from "react-router-dom";

export const Link = (props: LinkProps) => {
  const { children, className, ...propsToPass } = props;

  return (
    <RouterLink
      {...propsToPass}
      className={classNames("cursor-pointer underline hover:bg-gray-50 rounded-md", className)}
    >
      {children}
    </RouterLink>
  );
};
