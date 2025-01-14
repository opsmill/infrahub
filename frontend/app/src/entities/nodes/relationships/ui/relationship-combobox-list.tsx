import { relationshipsInfiniteQueryOptions } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships.query";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { AddRelationshipAction } from "@/entities/nodes/relationships/ui/add-relationship-action";
import { useSchema } from "@/entities/schema/hooks/useSchema";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ComboboxEmpty, ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";
import { Spinner } from "@/shared/components/ui/spinner";
import { debounce } from "@/shared/utils/common";
import { useInfiniteQuery } from "@tanstack/react-query";
import React, { forwardRef } from "react";

export interface RelationshipComboboxListProps {
  peer: string;
  onSelect: (value: RelationshipNode) => void;
  value?: RelationshipNode | null;
  filterItem?: (relationshipNode: RelationshipNode) => boolean;
}

export const RelationshipComboboxList = forwardRef<HTMLDivElement, RelationshipComboboxListProps>(
  ({ peer, value, onSelect, filterItem }, ref) => {
    const [search, setSearch] = React.useState("");
    const { schema } = useSchema(peer);
    const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
      useInfiniteQuery(relationshipsInfiniteQueryOptions({ peer, search }));

    if (error) return <ErrorScreen message={error.message} />;

    const setSearchDebounced = debounce(setSearch, 300);

    return (
      <>
        <ComboboxList
          ref={ref}
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
                    value={node.id}
                    selectedValue={value?.id}
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
);
