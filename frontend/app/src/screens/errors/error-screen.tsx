import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { ReactElement } from "react";

type tNoData = {
  className?: string;
  message?: string;
  icon?: ReactElement;
  hideIcon?: boolean;
};

const DEFAULT_MESSAGE = "Sorry, something went wrong.";

export default function ErrorScreen({ className, message, icon, hideIcon }: tNoData) {
  return (
    <div className={classNames("flex flex-col flex-1 items-center justify-center p-8", className)}>
      {!hideIcon && (
        <div className="bg-custom-white rounded-full text-red-300">
          {icon || <Icon icon={"mdi:warning-circle-outline"} className="text-3xl" />}
        </div>
      )}
      <div>{message ?? DEFAULT_MESSAGE}</div>
    </div>
  );
}
