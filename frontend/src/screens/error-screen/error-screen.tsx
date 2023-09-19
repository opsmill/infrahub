import { XCircleIcon } from "@heroicons/react/24/outline";
import { ReactElement } from "react";

type tNoData = {
  message?: string;
  icon?: ReactElement;
};

const DEFAULT_MESSAGE = "Sorry, something went wrong.";

export default function NoDataFound(props: tNoData) {
  const { message, icon } = props;

  return (
    <div className="flex flex-col flex-1 items-center justify-center p-8">
      <div className="bg-custom-white rounded-full p-4 text-custom-blue-green">
        {icon || <XCircleIcon className="h-8 w-8" />}
      </div>
      <div className="pt-2">{message ?? DEFAULT_MESSAGE}</div>
    </div>
  );
}
