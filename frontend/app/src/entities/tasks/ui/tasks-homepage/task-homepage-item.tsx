import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import type { TaskNode } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";

export const TaskHomepageItem = ({ id, title, branch, updated_at, related_nodes }: TaskNode) => {
  return (
    <div className="flex w-full flex-col gap-1.5 rounded-md border border-transparent bg-white p-2 text-xs shadow-sm">
      <Link
        className={classNames(
          focusVisibleStyle,
          "line-clamp-2 font-semibold transition-colors hover:text-custom-blue-700"
        )}
        to={constructPath(`/tasks/${id}`)}
      >
        {title}
      </Link>

      {related_nodes && related_nodes.length > 0 && (
        <div className="flex flex-wrap items-center gap-1">
          <Icon icon="mdi:cube-outline" className="shrink-0 text-gray-500" />
          {related_nodes.map((node) =>
            node ? (
              <Link
                key={node.id}
                className={classNames(
                  focusVisibleStyle,
                  "rounded px-1 py-0.5 text-gray-600 transition-colors hover:bg-gray-100 hover:text-custom-blue-700"
                )}
                to={getObjectDetailsUrl(node.kind, node.id)}
              >
                <NodeLabel id={node.id} kind={node.kind} branch={branch} />
              </Link>
            ) : null
          )}
        </div>
      )}

      <span className="flex items-center gap-1 text-gray-500">
        <Icon icon={"mdi:source-branch"} />
        <span className="truncate">{branch}</span>
      </span>
      <DateDisplay date={updated_at} dateFormat="d MMM yyyy HH:mm:ss" className="text-gray-500" />
    </div>
  );
};
