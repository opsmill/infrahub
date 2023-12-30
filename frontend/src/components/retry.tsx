import { ArrowPathIcon } from "@heroicons/react/24/outline";
import { useContext } from "react";
import { AuthContext } from "../decorators/withAuth";
import { classNames } from "../utils/common";

type tRetryProps = {
  isInProgress?: boolean;
  onClick?: Function;
};

export const Retry = (props: tRetryProps) => {
  const { isInProgress, onClick } = props;

  const auth = useContext(AuthContext);

  const handleClick = (event: any) => {
    if (!auth?.permissions?.write) {
      return;
    }

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
        "p-1 rounded-full",
        isInProgress ? "cursor-not-allowed " : "",
        auth?.permissions?.write ? "cursor-pointer hover:bg-gray-200" : "cursor-not-allowed"
      )}
      onClick={handleClick}>
      <ArrowPathIcon className={classNames("h-4 w-4", isInProgress ? "text-gray-400" : "")} />
    </div>
  );
};
