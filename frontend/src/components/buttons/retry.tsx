import { Icon } from "@iconify-icon/react";
import { classNames } from "../../utils/common";

type tRetryProps = {
  isLoading?: boolean;
  onClick?: Function;
  isDisabled?: boolean;
  className?: string;
};

export const Retry = (props: tRetryProps) => {
  const { isLoading, onClick, isDisabled, className = "" } = props;

  const handleClick = (event: any) => {
    if (isDisabled) {
      return;
    }

    if (isLoading) {
      return;
    }

    if (onClick) {
      onClick(event);
    }
  };

  return (
    <div
      className={classNames(
        "flex items-center p-1 rounded-full cursor-pointer",
        isLoading ? "animate-spin" : "",
        isLoading || isDisabled ? "!cursor-not-allowed" : "",
        className?.includes("hover:") ? "" : "hover:bg-gray-200"
      )}
      onClick={handleClick}>
      <Icon
        icon={"mdi:circle-arrows"}
        className={classNames("h-4 w-4", isLoading ? "text-gray-300" : "text-gray-400")}
      />
    </div>
  );
};
