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
      cardinality: "one",
    },
  },
];

export const GlobalEventsFilters = () => {
  return (
    <TagGroup className="flex" selectionMode="single">
      <TagList className="flex items-center gap-2 py-3">
        {FILTERS.map((filter) => {
          return <GlobalFilter key={filter.name} {...filter} />;
        })}
      </TagList>
    </TagGroup>
  );
};
