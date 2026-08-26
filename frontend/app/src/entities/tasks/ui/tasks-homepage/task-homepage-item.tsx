import { Card } from "@infrahub/ui";
import { Link } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import { Icon } from "@/shared/components/display/icon";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";
import type { TaskHomepageNode } from "@/entities/tasks/domain/use-cases/get-tasks-homepage";

export const TaskHomepageItem = ({
  id,
  title,
  branch,
  updated_at,
  related_nodes,
}: TaskHomepageNode) => {
  return (
    <Card className="w-full gap-1.5 rounded-md p-2 text-xs">
      <Link
        className={classNames(
          focusVisibleStyle,
          "line-clamp-2 font-semibold transition-colors",
          "hover:text-accent"
        )}
        to={constructPath(`/tasks/${id}`)}
      >
        {title}
      </Link>

      {related_nodes && related_nodes.length > 0 && (
        <div className="flex flex-wrap items-center gap-1">
          {related_nodes.map((node) => {
            if (!node) return null;

            const { schema } = getSchema(node.kind);
            const icon = getSchemaIcon(schema);

            return (
              <Link
                key={node.id}
                className={classNames(
                  focusVisibleStyle,
                  "flex items-center gap-1 rounded px-1 py-0.5 text-foreground-muted transition-colors",
                  "hover:bg-highlight hover:text-accent"
                )}
                to={getObjectDetailsUrl(node.kind, node.id)}
              >
                <Icon icon={icon} className="shrink-0" />
                <NodeLabel id={node.id} kind={node.kind} branch={branch} />
              </Link>
            );
          })}
        </div>
      )}

      <span className="flex items-center gap-1 text-foreground-muted">
        <Icon icon={"mdi:source-branch"} />
        <span className="truncate">{branch}</span>
      </span>
      <DateDisplay date={updated_at} className="text-foreground-muted" />
    </Card>
  );
};
