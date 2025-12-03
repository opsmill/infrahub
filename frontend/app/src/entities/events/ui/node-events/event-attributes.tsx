import { ChevronRightIcon } from "lucide-react";
import React from "react";

import type { NodeMutatedEvent } from "@/shared/api/graphql/generated/graphql";
import { Card } from "@/shared/components/ui/card";

export const EventAttributes = ({ attributes }: Pick<NodeMutatedEvent, "attributes">) => {
  if (attributes.length === 0) return null;

  return (
    <Card className="grid grid-cols-[min-content_auto] gap-1.5 bg-zinc-50 text-xs dark:bg-slate-600">
      {attributes.map(({ action, name, value, value_previous }) => {
        return (
          <React.Fragment key={`${action}_${name}`}>
            <div className="mr-2 truncate text-left text-gray-600 dark:text-gray-300">{name}</div>

            <div className="flex items-center gap-2 overflow-hidden">
              <div className="text-gray-400 dark:text-gray-500">{value_previous ?? "-"}</div>

              <ChevronRightIcon className="size-3 text-custom-blue-500" />

              <div className="overflow-hidden text-ellipsis dark:text-gray-200">{value ?? "-"}</div>
            </div>
          </React.Fragment>
        );
      })}
    </Card>
  );
};
