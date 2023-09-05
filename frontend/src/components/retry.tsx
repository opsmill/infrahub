import { ArrowPathIcon } from "@heroicons/react/24/outline";
import { classNames } from "../utils/common";

type tRetryProps = {
  isInProgress?: boolean;
  onClick?: Function;
};

export const Retry = (props: tRetryProps) => {
  const { isInProgress, onClick } = props;

  const handleClick = (event: any) => {
    if (isInProgress) {
      return;
    }

    if (onClick) {
      onClick(event);
    }
  };

  return (
    <div
      className={classNames(
        "ml-2 p-1 rounded-full",
        isInProgress ? "cursor-not-allowed " : " cursor-pointer hover:bg-gray-200"
      )}
      onClick={handleClick}>
      <ArrowPathIcon className={classNames("h-4 w-4", isInProgress ? "text-gray-400" : "")} />
    </div>
  );
};
