import { ComboboxEmpty, ComboboxItem, ComboboxList } from "@/components/ui/combobox";
import { Spinner } from "@/components/ui/spinner";
import { useSchema } from "@/hooks/useSchema";
import ErrorScreen from "@/screens/errors/error-screen";
import { AddRelationshipAction } from "@/screens/objects/relationships/components/add-relationship-action";
import { relationshipsInfiniteQueryOptions } from "@/screens/objects/relationships/domain/get-relationships";
import { RelationshipNode } from "@/screens/objects/relationships/domain/types";
import { useInfiniteQuery } from "@tanstack/react-query";
import React from "react";

export function RelationshipComboboxList({
  peer,
  onSelect,
}: {
  peer: string;
  onSelect: (value: RelationshipNode) => void;
}) {
  const [search, setSearch] = React.useState("");
  const { schema } = useSchema(peer);
  const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteQuery(relationshipsInfiniteQueryOptions({ peer, search }));

  if (error) return <ErrorScreen message={error.message} />;

  return (
    <>
      <ComboboxList
        autoFocus
        onValueChange={(newValue) => setSearch(newValue)}
        shouldFilter={false}
      >
        {isPending ? (
          <Spinner className="flex justify-center m-2" />
        ) : (
          <>
            <ComboboxEmpty>No {schema?.label ?? "results"} found</ComboboxEmpty>

            {data.pages.map((page) =>
              page.map((node) => (
                <ComboboxItem
                  key={node.id}
                  value={node.display_label}
                  onSelect={() => onSelect(node)}
                >
                  <span className="truncate">{node.display_label}</span>
                </ComboboxItem>
              ))
            )}
          </>
        )}

        {hasNextPage && (
          <ComboboxItem
            value="Load more"
            onSelect={() => fetchNextPage()}
            disabled={!hasNextPage || isFetchingNextPage}
          >
            {isFetchingNextPage ? "Loading more..." : "Load more"}
          </ComboboxItem>
        )}
      </ComboboxList>

      <AddRelationshipAction peer={peer} onSuccess={onSelect} />
    </>
  );
}
