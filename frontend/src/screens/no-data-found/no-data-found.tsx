import { DocumentTextIcon } from "@heroicons/react/24/outline";
import { ReactElement } from "react";

type tNoData = {
  message?: string;
  icon?: ReactElement;
};

const DEFAULT_MESSAGE = "Sorry, no data found.";

export default function NoDataFound(props: tNoData) {
  const { message, icon } = props;

  return (
    <div className="flex flex-col items-center justify-center p-8 border-b border-gray-200">
      <div className="bg-custom-white rounded-full p-4 text-custom-blue-green">
        {icon || <DocumentTextIcon className="h-8 w-8" />}
      </div>
      <div className="mt-4">{message ?? DEFAULT_MESSAGE}</div>
    </div>
  );
}
