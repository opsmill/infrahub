import { DocumentTextIcon } from "@heroicons/react/24/outline";
import { ReactElement } from "react";
import { classNames } from "../../utils/common";

type tNoData = {
  className?: string;
  message?: string;
  icon?: ReactElement;
};

const DEFAULT_MESSAGE = "Sorry, no data found.";

export default function NoDataFound(props: tNoData) {
  const { className = "", message, icon } = props;

  return (
    <div
      className={classNames(
        "flex flex-col items-center justify-center p-8 border-b border-gray-200",
        className
      )}>
      <div className="bg-custom-white rounded-full p-4 text-custom-blue-green">
        {icon || <DocumentTextIcon className="h-8 w-8" />}
      </div>
      <div>{message ?? DEFAULT_MESSAGE}</div>
    </div>
  );
}
