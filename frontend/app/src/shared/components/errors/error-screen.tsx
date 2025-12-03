import { Icon } from "@iconify-icon/react";
import type { ReactNode } from "react";

import { classNames } from "@/shared/utils/common";

type tNoData = {
  className?: string;
  message?: ReactNode;
  icon?: ReactNode;
  hideIcon?: boolean;
};

const DEFAULT_MESSAGE = "Sorry, something went wrong.";

export default function ErrorScreen({ className, message, icon, hideIcon }: tNoData) {
  return (
    <div className={classNames("flex flex-1 flex-col items-center justify-center p-8", className)}>
      {!hideIcon && (
        <div className="rounded-full bg-white text-red-300 dark:bg-slate-700 dark:text-red-400">
          {icon || <Icon icon={"mdi:warning-circle-outline"} className="text-3xl" />}
        </div>
      )}
      <div className="dark:text-gray-300">{message ?? DEFAULT_MESSAGE}</div>
    </div>
  );
}
