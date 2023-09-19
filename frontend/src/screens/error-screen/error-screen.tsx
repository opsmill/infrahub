import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { ReactElement } from "react";

type tNoData = {
  message?: string;
  icon?: ReactElement;
};

const DEFAULT_MESSAGE = "Sorry, something went wrong.";

export default function ErrorScreen(props: tNoData) {
  const { message, icon } = props;

  return (
    <div className="flex flex-col flex-1 items-center justify-center p-8">
      <div className="bg-custom-white rounded-full p-4 text-red-300">
        {icon || <ExclamationCircleIcon className="h-8 w-8" />}
      </div>
      <div className="mt-4">{message ?? DEFAULT_MESSAGE}</div>
    </div>
  );
}
