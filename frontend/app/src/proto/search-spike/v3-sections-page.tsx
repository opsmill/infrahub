// @ts-nocheck
import { Command } from "cmdk";
import { ArrowRightIcon } from "lucide-react";

import { CommandItem } from "@/shared/components/ui/command";
import Kbd from "@/shared/components/ui/kbd";

import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";

import { searchExactOnly, searchPartialOnly } from "./data";
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

/** Two sections: exact matches above other matches; "View all results" opens a results page. */
export function SectionsPageVariant() {
  const { query, caseSensitive, showResultsPage } = useProto();
  const key = String(caseSensitive);
  const exact = useFakeSearch(query, (q) => searchExactOnly(q, caseSensitive, 4), { key });
  const partial = useFakeSearch(query, (q) => searchPartialOnly(q, caseSensitive, 4), { key });

  const hasExact = exact.status === "success" && exact.data.total > 0;
  const total = (exact.data?.total ?? 0) + (partial.data?.total ?? 0);
  const canViewAll = exact.status === "success" && partial.status === "success" && total > 0;

  return (
    <SearchDialogShell>
      <Command shouldFilter={false}>
        <SearchInput
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && canViewAll) {
              e.preventDefault();
              showResultsPage();
            }
          }}
        />
        <Command.List className="[&_[cmdk-group]]:mt-2">
          <GoToGroup />
          <ParentPrefixesGroup prefixes={partial.data?.parentPrefixes} />

          {exact.status === "loading" && <LoadingObjects heading="Exact match" />}
          {hasExact && (
            <SearchAnywhereGroup
              heading={
                exact.data.total === 1 ? (
                  "Exact match"
                ) : (
                  <span className="tabular-nums">Exact matches · {exact.data.total}</span>
                )
              }
            >
              {exact.data.nodes.map((node) => (
                <NodeRow key={node.id} node={node} />
              ))}
            </SearchAnywhereGroup>
          )}

          {partial.status === "loading" && <LoadingObjects heading={hasExact ? "Other matches" : "Objects"} />}
          {partial.status === "success" && partial.data.total > 0 && (
            <SearchAnywhereGroup
              heading={
                <span className="tabular-nums">
                  {hasExact ? "Other matches" : "Objects"} · {partial.data.total}
                </span>
              }
            >
              {partial.data.nodes.map((node) => (
                <NodeRow key={node.id} node={node} />
              ))}
            </SearchAnywhereGroup>
          )}

          {canViewAll && total > 4 && (
            <SearchAnywhereGroup>
              <CommandItem value="view-all" onSelect={showResultsPage} className="text-foreground">
                <ArrowRightIcon aria-hidden="true" className="mx-2 size-4 text-subtle" />
                <span className="min-w-0 truncate tabular-nums">
                  View all {total} results for “{query.trim()}”
                </span>
                <Kbd keys={["command", "enter"]} className="ml-auto bg-surface" />
              </CommandItem>
            </SearchAnywhereGroup>
          )}

          <DocsGroup />
        </Command.List>
      </Command>
    </SearchDialogShell>
  );
}
