// @ts-nocheck
import { Command } from "cmdk";

import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";

import { searchToday } from "./data";
import {
  DocsGroup,
  GoToGroup,
  LoadingObjects,
  NodeRow,
  ParentPrefixesGroup,
  SearchDialogShell,
  SearchInput,
  useFakeSearch,
  useProto,
} from "./shared";

/** Today: partial match ordered by id, first 4, no way to view the rest. */
export function CurrentVariant() {
  const { query, caseSensitive } = useProto();
  const search = useFakeSearch(query, (q) => searchToday(q, caseSensitive), { key: String(caseSensitive) });

  return (
    <SearchDialogShell>
      <Command shouldFilter={false}>
        <SearchInput />
        <Command.List className="[&_[cmdk-group]]:mt-2">
          <GoToGroup />
          <ParentPrefixesGroup prefixes={search.data?.parentPrefixes} />
          {search.status === "loading" && <LoadingObjects />}
          {search.status === "success" && search.data.nodes.length > 0 && (
            <SearchAnywhereGroup heading="Objects">
              {search.data.nodes.map((node) => (
                <NodeRow key={node.id} node={node} />
              ))}
            </SearchAnywhereGroup>
          )}
          <DocsGroup />
        </Command.List>
      </Command>
    </SearchDialogShell>
  );
}
