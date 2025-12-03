import { Icon } from "@iconify-icon/react";
import type { ReactElement, ReactNode } from "react";

type tNoData = {
  message?: ReactNode;
  icon?: ReactElement;
};

const DEFAULT_MESSAGE = "Sorry, no data found.";

export default function NoDataFound(props: tNoData) {
  const { message, icon } = props;

  return (
    <div className="col-span-full flex flex-col items-center justify-center py-12 text-stone-500 dark:text-stone-400">
      {icon ?? <Icon icon="mdi:table-off" className="mb-2 text-3xl" />}
      <div className="font-medium text-lg">No data</div>
      <div className="text-sm">{message ?? DEFAULT_MESSAGE}</div>
    </div>
  );
}
