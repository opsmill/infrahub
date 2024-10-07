import { classNames } from "@/utils/common";
import React from "react";

export const Divider = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => {
  return (
    <div
      className={classNames(
        "py-3 w-full flex items-center text-sm text-gray-800 before:flex-1 before:border-t before:border-gray-200 before:me-6 after:flex-1 after:border-t after:border-gray-200 after:ms-6",
        className
      )}
      {...props}
    />
  );
};
