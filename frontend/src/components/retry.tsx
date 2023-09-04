import { ArrowPathIcon } from "@heroicons/react/24/outline";
import { classNames } from "../utils/common";

type tRetryProps = {
  isInProgress?: BooleanConstructor;
  onClick?: Function;
};

export const Retry = (props: tRetryProps) => {
  const { isInProgress, onClick } = props;

  const handleClick = (event: any) => {
    if (onClick) {
      onClick(event);
    }
  };

  return (
    <div
      className={classNames(
        "ml-2 p-1 rounded-full",
        isInProgress ? "animate-spin cursor-not-allowed " : " cursor-pointer hover:bg-gray-200"
      )}
      onClick={handleClick}>
      <ArrowPathIcon className="h-4 w-4 " />
    </div>
  );
};
