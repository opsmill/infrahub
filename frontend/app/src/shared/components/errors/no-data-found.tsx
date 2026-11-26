import type { ReactElement, ReactNode } from "react";

import { Icon } from "@/shared/components/display/icon";

type tNoData = {
  title?: ReactNode;
  message?: ReactNode;
  icon?: ReactElement;
};

const DEFAULT_MESSAGE = "Sorry, no data found.";

export default function NoDataFound(props: tNoData) {
  const { title = "No data", message, icon } = props;

  return (
    <div className="col-span-full flex flex-col items-center justify-center py-12 text-foreground-muted">
      {icon ?? <Icon icon="mdi:table-off" className="mb-2 text-3xl" />}
      <div className="font-medium text-lg">{title}</div>
      <div className="text-sm">{message ?? DEFAULT_MESSAGE}</div>
    </div>
  );
}
