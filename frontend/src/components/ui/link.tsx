import { Link as RouterLink } from "react-router-dom";
import { classNames } from "../../utils/common";

type LinkProps = {
  to: string;
  children?: any;
  target?: string;
  className?: string;
};

export const Link = (props: LinkProps) => {
  const { children, className, ...propsToPass } = props;

  return (
    <RouterLink
      {...propsToPass}
      className={classNames("cursor-pointer underline hover:bg-gray-50 rounded-md", className)}>
      {children}
    </RouterLink>
  );
};
