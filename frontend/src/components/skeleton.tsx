import { HTMLAttributes } from "react";
import { classNames } from "../utils/common";

export const Skeleton = ({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) => {
  return (
    <div
      className={classNames(
        "animate-[pulse_1s_ease-in-out_infinite] rounded-md bg-custom-blue-700/20",
        className
      )}
      {...props}
    />
  );
};
