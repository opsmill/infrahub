import { TagGroup, TagList } from "react-aria-components";

import { ScrollArea } from "@/shared/components/ui/scroll-area";

import { EVENT_TYPE_CHOICES } from "@/entities/events/constants";

import { GlobalBranchFilter } from "./global-branch-filter";
import { GlobalFilter } from "./global-filter";
import { GlobalKindFilter } from "./global-kind-filter";

export const GlobalEventsFilters = () => {
  return (
    <ScrollArea scrollX>
      <TagGroup className="flex" selectionMode="single" aria-label="Filter group">
        <TagList className="flex items-center gap-2">
          <GlobalBranchFilter />

          <GlobalFilter
            name="eventType"
            label="Event Type"
            fieldSchema={{
              kind: "Dropdown",
              choices: EVENT_TYPE_CHOICES,
            }}
          />

          <GlobalFilter
            name="hasChildren"
            label="Has Children"
            fieldSchema={{
              kind: "Boolean",
            }}
          />

          <GlobalKindFilter name="primaryNodeIds" label="Primary Node" />

          <GlobalKindFilter name="relatedNodeIds" label="Related Node" />

          <GlobalFilter
            name="accountIds"
            label="Account"
            fieldSchema={{
              peer: "CoreAccount",
            }}
          />

          <GlobalFilter
            name="since"
            label="Start Date"
            fieldSchema={{
              kind: "DateTime",
            }}
          />

          <GlobalFilter
            name="until"
            label="End Date"
            fieldSchema={{
              kind: "DateTime",
            }}
          />
        </TagList>
      </TagGroup>
    </ScrollArea>
  );
};
