import { branchesState } from "@/entities/branches/stores";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { useAtomValue } from "jotai";
import { TagGroup, TagList } from "react-aria-components";
import { EVENT_TYPE_CHOICES } from "../../constants";
import { GlobalBranchFilter } from "./global-branch-filter";
import { GlobalFilter } from "./global-filter";
import { GlobalKindFilter } from "./global-kind-filter";

export const GlobalEventsFilters = () => {
  const branches = useAtomValue(branchesState);

  return (
    <ScrollArea scrollX>
      <TagGroup className="flex" selectionMode="single" aria-label="Filter group">
        <TagList className="flex items-center gap-2">
          <GlobalBranchFilter
            name="branches"
            label="Branch"
            fieldSchema={{
              kind: "Dropdown",
              choices: branches.map((branch) => {
                return {
                  label: branch.name,
                  name: branch.name,
                };
              }),
            }}
          />

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
