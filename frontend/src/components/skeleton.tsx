import { HTMLAttributes } from "react";
import { classNames } from "../utils/common";

export const Skeleton = ({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) => {
  return (
    <div
      className={classNames(
        "animate-pulse duration-150 rounded-md bg-custom-blue-700/25",
        className
      )}
      {...props}
    />
  );
};
