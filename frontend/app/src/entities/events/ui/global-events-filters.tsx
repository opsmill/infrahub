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
    name: "test",
    label: "Test",
    fieldSchema: {
      kind: "Text",
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
