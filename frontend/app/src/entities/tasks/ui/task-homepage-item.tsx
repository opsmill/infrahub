import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import type { TaskNode } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import { classNames } from "@/shared/utils/common";

import { TaskHomepageCard } from "./task-homepage-card";

export const TaskHomepageItem = ({ id, title, branch, updated_at }: TaskNode) => {
  return (
    <Link className={"flex flex-col gap-2 text-sm"} to={constructPath(`/tasks/${id}`)}>
      <TaskHomepageCard className={classNames("transition-all hover:bg-gray-50")}>
        <span className="font-semibold">{title}</span>
        <span className="flex items-center gap-1 text-gray-500">
          <Icon icon={"mdi:source-branch"} />
          {branch}
        </span>
        <DateDisplay date={updated_at} dateFormat="d MMM yyyy HH:mm:ss" className="text-gray-500" />
      </TaskHomepageCard>
    </Link>
  );
};
