// @ts-nocheck
import { Command } from "cmdk";
import { ChevronsDownIcon } from "lucide-react";
import React from "react";

import { CommandItem } from "@/shared/components/ui/command";

import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";

import { isExact, searchExactFirst } from "./data";
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

/** One list: exact matches sorted to the top and tagged; "Show all results" grows the same list in place. */
export function OneListVariant() {
  const { query, caseSensitive } = useProto();
  const [selected, setSelected] = React.useState("");
  const [showAllFor, setShowAllFor] = React.useState<string | null>(null);
  const showAll = showAllFor === `${query.trim()}|${caseSensitive}`;

  const first = useFakeSearch(query, (q) => searchExactFirst(q, caseSensitive, 4), { key: String(caseSensitive) });
  const all = useFakeSearch(query, (q) => searchExactFirst(q, caseSensitive, 0), {
    key: String(caseSensitive),
    enabled: showAll,
    delay: [900, 1600],
  });

  const result = all.status === "success" ? all.data : first.data;

  return (
    <SearchDialogShell>
      <Command shouldFilter={false} value={selected} onValueChange={setSelected}>
        <SearchInput />
        <Command.List className="max-h-[75vh] overflow-y-auto [&_[cmdk-group]]:mt-2">
          <GoToGroup />
          <ParentPrefixesGroup prefixes={first.data?.parentPrefixes} />
          {first.status === "loading" && <LoadingObjects />}
          {result && result.nodes.length > 0 && (
            <SearchAnywhereGroup
              heading={
                all.status === "success" ? (
                  <span className="tabular-nums">All {result.total} objects</span>
                ) : (
                  "Objects"
                )
              }
            >
              {result.nodes.map((node) => (
                <NodeRow key={node.id} node={node} exact={isExact(node, query, caseSensitive)} />
              ))}

              {result.hasMore && !showAll && (
                <CommandItem
                  value="show-all"
                  onSelect={() => {
                    setSelected(result.nodes[result.nodes.length - 1].id);
                    setShowAllFor(`${query.trim()}|${caseSensitive}`);
                  }}
                  className="text-foreground"
                >
                  <ChevronsDownIcon aria-hidden="true" className="mx-2 size-4 text-subtle" />
                  Show all results
                </CommandItem>
              )}

              {showAll && all.status === "loading" && (
                <CommandItem disabled value="loading-all" className="text-subtle">
                  <span
                    aria-hidden="true"
                    className="mx-2 size-4 animate-spin rounded-full border-2 border-border-strong border-t-accent"
                  />
                  Loading all results…
                </CommandItem>
              )}
            </SearchAnywhereGroup>
          )}
          <DocsGroup />
        </Command.List>
      </Command>
    </SearchDialogShell>
  );
}
