import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import type { TaskNode } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export const TaskHomepageItem = ({ id, title, branch, updated_at }: TaskNode) => {
  return (
    <Link
      className={classNames(
        focusVisibleStyle,
        "flex w-full flex-col gap-1.5 rounded-md border border-transparent bg-white p-2 text-xs shadow-sm"
      )}
      to={constructPath(`/tasks/${id}`)}
    >
      <span className="line-clamp-2 font-semibold">{title}</span>
      <span className="flex items-center gap-1 text-gray-500">
        <Icon icon={"mdi:source-branch"} />
        <span className="truncate">{branch}</span>
      </span>
      <DateDisplay date={updated_at} dateFormat="d MMM yyyy HH:mm:ss" className="text-gray-500" />
    </Link>
  );
};
