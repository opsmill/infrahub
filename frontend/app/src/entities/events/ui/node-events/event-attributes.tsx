import { Card, CardContent } from "@infrahub/ui";
import { ChevronRightIcon } from "lucide-react";
import React from "react";

import type { NodeMutatedEvent } from "@/shared/api/graphql/generated/types";

export const EventAttributes = ({ attributes }: Pick<NodeMutatedEvent, "attributes">) => {
  if (attributes.length === 0) return null;

  return (
    <Card className="bg-background">
      {/* biome-ignore lint/nursery/noTailwindArbitraryValue: structure: single-site intrinsic track list; min-content is structural, not a design value */}
      <CardContent className="grid grid-cols-[min-content_auto] gap-1.5 text-xs">
        {attributes.map(({ action, name, value, value_previous }) => {
          return (
            <React.Fragment key={`${action}_${name}`}>
              <div className="mr-2 truncate text-left text-subtle">{name}</div>

              <div className="flex items-center gap-2 overflow-hidden">
                <div className="text-subtle-muted">{value_previous ?? "-"}</div>

                <ChevronRightIcon className="size-3 text-accent" />

                <div className="overflow-hidden text-ellipsis">{value ?? "-"}</div>
              </div>
            </React.Fragment>
          );
        })}
      </CardContent>
    </Card>
  );
};
