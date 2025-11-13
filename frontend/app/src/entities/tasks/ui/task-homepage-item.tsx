import { Icon } from "@iconify-icon/react";

import type { TaskNode } from "@/shared/api/graphql/generated/graphql";
import { DateDisplay } from "@/shared/components/display/date-display";

export const TaskHomepageItem = ({ title, branch, updated_at }: TaskNode) => {
  return (
    <div className={"flex flex-col gap-2 text-sm"}>
      <span className="font-semibold">{title}</span>
      <span className="flex items-center gap-1 text-gray-500">
        <Icon icon={"mdi:source-branch"} />
        {branch}
      </span>
      <DateDisplay date={updated_at} dateFormat="d MMM yyyy HH:mm:ss" className="text-gray-500" />
    </div>
  );
};
