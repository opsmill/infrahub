import { Icon } from "@iconify-icon/react";
import { ReactElement, ReactNode } from "react";

type tNoData = {
  message?: ReactNode;
  icon?: ReactElement;
};

const DEFAULT_MESSAGE = "Sorry, no data found.";

export default function NoDataFound(props: tNoData) {
  const { message, icon } = props;

  return (
    <div className="flex flex-col flex-1 items-center justify-center p-8 text-center gap-2">
      <div className="bg-custom-white rounded-full flex items-center justify-center p-2 text-custom-blue-green">
        {icon || <Icon icon={"mdi:file-question-outline"} className="" />}
      </div>
      <div>{message ?? DEFAULT_MESSAGE}</div>
    </div>
  );
}
