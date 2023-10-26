import { Link as RouterLink } from "react-router-dom";

type LinkProps = {
  to: string;
  children?: any;
  target?: string;
};

export const Link = (props: LinkProps) => {
  const { children, ...propsToPass } = props;

  return (
    <RouterLink {...propsToPass} className="cursor-pointer underline">
      {children}
    </RouterLink>
  );
};
