import { HTMLAttributes } from "react";
import { classNames } from "../../utils/common";

const Content = ({ className, ...props }: HTMLAttributes<HTMLElement>) => {
  return <main className={classNames("h-full overflow-auto", className)} {...props} />;
};

export default Content;
