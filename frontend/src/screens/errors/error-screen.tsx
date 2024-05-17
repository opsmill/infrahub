import { Icon } from "@iconify-icon/react";
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
      <div className="bg-custom-white rounded-full text-red-300">
        {icon || <Icon icon={"mdi:warning-circle-outline"} className="text-3xl" />}
      </div>
      <div>{message ?? DEFAULT_MESSAGE}</div>
    </div>
  );
}
