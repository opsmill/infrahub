import { Icon } from "@iconify-icon/react";
import { classNames } from "../../utils/common";

type tRetryProps = {
  isLoading?: boolean;
  onClick?: Function;
  isDisabled?: boolean;
};

export const Retry = (props: tRetryProps) => {
  const { isLoading, onClick, isDisabled } = props;

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
        "flex items-center p-1 rounded-full",
        isLoading ? "cursor-not-allowed animate-spin" : "",
        !isLoading && isDisabled ? "cursor-pointer hover:bg-gray-200" : "cursor-not-allowed"
      )}
      onClick={handleClick}>
      <Icon
        icon={"mdi:circle-arrows"}
        className={classNames("h-4 w-4", isLoading ? "text-gray-300" : "text-gray-400")}
      />
    </div>
  );
};
