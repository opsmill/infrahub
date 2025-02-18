import { branchesState } from "@/entities/branches/stores";
import { branchesToSelectOptions } from "@/entities/branches/utils";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { store } from "@/shared/stores";
import { TagGroup, TagList } from "react-aria-components";
import { GlobalFilter } from "./global-filter";

const FILTERS = [
  {
    name: "hasChildren",
    label: "Has Children",
    fieldSchema: {
      kind: "Boolean",
    },
  },
  {
    name: "branches",
    label: "Branch",
    fieldSchema: {
      kind: "Dropdown",
      choices: branchesToSelectOptions(store.get(branchesState)).map((branch) => {
        return {
          label: branch.name,
          name: branch.name,
        };
      }),
    },
  },
  {
    name: "eventType",
    label: "Event Type",
    fieldSchema: {
      kind: "Dropdown",
      choices: [
        {
          label: "Node update",
          name: "NodeMutatedEvent",
        },
      ],
    },
  },
  {
    name: "primaryNodeIds",
    label: "Primary Node",
    fieldSchema: {
      peer: "CoreNode",
    },
  },
  {
    name: "relatedNodeIds",
    label: "Related Node",
    fieldSchema: {
      peer: "CoreNode",
    },
  },
  {
    name: "accountIds",
    label: "Account",
    fieldSchema: {
      peer: "CoreAccount",
    },
  },
  {
    name: "since",
    label: "Start Date",
    fieldSchema: {
      kind: "DateTime",
    },
  },
  {
    name: "until",
    label: "End Date",
    fieldSchema: {
      kind: "DateTime",
    },
  },
];

export const GlobalEventsFilters = () => {
  return (
    <ScrollArea scrollX>
      <TagGroup className="flex" selectionMode="single">
        <TagList className="flex items-center gap-2 py-3">
          {FILTERS.map((filter) => {
            return <GlobalFilter key={filter.name} {...filter} />;
          })}
        </TagList>
      </TagGroup>
    </ScrollArea>
  );
};
