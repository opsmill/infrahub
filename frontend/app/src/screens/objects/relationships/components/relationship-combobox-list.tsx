import { ComboboxEmpty, ComboboxItem, ComboboxList } from "@/components/ui/combobox";
import { Spinner } from "@/components/ui/spinner";
import { useSchema } from "@/hooks/useSchema";
import ErrorScreen from "@/screens/errors/error-screen";
import { AddRelationshipAction } from "@/screens/objects/relationships/components/add-relationship-action";
import { relationshipsInfiniteQueryOptions } from "@/screens/objects/relationships/domain/get-relationships";
import { RelationshipNode } from "@/screens/objects/relationships/domain/types";
import { debounce } from "@/utils/common";
import { useInfiniteQuery } from "@tanstack/react-query";
import React from "react";

export interface RelationshipComboboxListProps {
  peer: string;
  onSelect: (value: RelationshipNode) => void;
  filterItem?: (relationshipNode: RelationshipNode) => boolean;
}

export function RelationshipComboboxList({
  peer,
  onSelect,
  filterItem,
}: RelationshipComboboxListProps) {
  const [search, setSearch] = React.useState("");
  const { schema } = useSchema(peer);
  const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteQuery(relationshipsInfiniteQueryOptions({ peer, search }));

  if (error) return <ErrorScreen message={error.message} />;

  const setSearchDebounced = debounce(setSearch, 300);

  return (
    <>
      <ComboboxList
        autoFocus
        onValueChange={(newValue) => setSearchDebounced(newValue)}
        shouldFilter={false}
      >
        {isPending ? (
          <Spinner className="flex justify-center m-2" />
        ) : (
          <>
            <ComboboxEmpty>No {schema?.label ?? "results"} found</ComboboxEmpty>

            {data.pages.map((page) => {
              const filteredNodes = filterItem ? page.filter(filterItem) : page;

              return filteredNodes.map((node) => (
                <ComboboxItem
                  key={node.id}
                  value={node.display_label}
                  onSelect={() => onSelect(node)}
                >
                  <span className="truncate">{node.display_label}</span>
                </ComboboxItem>
              ));
            })}
          </>
        )}

        {hasNextPage && (
          <ComboboxItem
            value="Load more"
            onSelect={() => fetchNextPage()}
            disabled={!hasNextPage || isFetchingNextPage}
            className="justify-center text-custom-blue-700"
          >
            {isFetchingNextPage ? "Loading more..." : "Load more"}
          </ComboboxItem>
        )}
      </ComboboxList>

      <AddRelationshipAction peer={peer} onSuccess={onSelect} />
    </>
  );
}
