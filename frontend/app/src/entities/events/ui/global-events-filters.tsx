import { branchesState } from "@/entities/branches/stores";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { useAtomValue } from "jotai";
import { TagGroup, TagList } from "react-aria-components";
import { GlobalFilter } from "./global-filter";

export const GlobalEventsFilters = () => {
  const branches = useAtomValue(branchesState);

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
        choices: branches.map((branch) => {
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
            label: "Node updated",
            name: "NodeMutatedEvent",
          },
          {
            label: "Branch created",
            name: "BranchCreatedEvent",
          },
          {
            label: "Branch updated",
            name: "BranchUpdatedEvent",
          },
          {
            label: "Branch rebased",
            name: "BranchRebasedEvent",
          },
          {
            label: "Standard event",
            name: "StandardEvent",
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
