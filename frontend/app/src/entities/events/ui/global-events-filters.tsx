import { branchesState } from "@/entities/branches/stores";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { useAtomValue } from "jotai";
import { TagGroup, TagList } from "react-aria-components";
import { FILTERS } from "../utils/constants";
import { GlobalBranchFilter } from "./global-branch-filter";
import { GlobalFilter } from "./global-filter";

export const GlobalEventsFilters = () => {
  const branches = useAtomValue(branchesState);

  return (
    <ScrollArea scrollX>
      <TagGroup className="flex" selectionMode="single" aria-label="Filter group">
        <TagList className="flex items-center gap-2 py-3">
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

          {FILTERS.map((filter) => {
            return <GlobalFilter key={filter.name} {...filter} />;
          })}
        </TagList>
      </TagGroup>
    </ScrollArea>
  );
};
