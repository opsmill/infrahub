import { Spinner } from "@infrahub/ui";
import React from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import {
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  type ComboboxListProps,
} from "@/shared/components/ui/combobox";
import { debounce } from "@/shared/utils/common";
import { isUuid } from "@/shared/utils/is-uuid";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { useRelationships } from "@/entities/nodes/relationships/ui/queries/get-relationships.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface RelationshipComboboxListProps
  extends Omit<ComboboxListProps, "value" | "onSelect"> {
  ref?: React.Ref<HTMLDivElement>;
  peer: string;
  onSelect: (value: RelationshipNode) => void;
  value?: RelationshipNode | null;
  filterItem?: (relationshipNode: RelationshipNode) => boolean;
  filterQuery?: Record<string, string | number | boolean | string[]>;
}

export const RelationshipComboboxList = ({
  ref,
  peer,
  value,
  onSelect,
  filterItem,
  filterQuery,
  ...props
}: RelationshipComboboxListProps) => {
  const [search, setSearch] = React.useState("");
  const { schema } = useSchema(peer);
  // When the user types or pastes a UUID, switch the underlying query from a
  // label search to an ids filter. UUID is a maximally specific match, so it
  // intentionally overrides any caller-provided filterQuery.
  const isUuidSearch = search.length > 0 && isUuid(search);
  const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useRelationships({
      peer,
      search: isUuidSearch ? undefined : search,
      filterQuery: isUuidSearch ? { ids: [search.trim()] } : filterQuery,
    });

  if (error) return <ErrorScreen message={error.message} />;

  const setSearchDebounced = debounce(setSearch, 300);

  return (
    <ComboboxList
      ref={ref}
      onValueChange={(newValue) => setSearchDebounced(newValue)}
      shouldFilter={false}
      placeholder="Search by name or UUID..."
      {...props}
    >
      {isPending ? (
        <Spinner className="m-2 flex justify-center" />
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
                <span className="truncate">{getNodeLabel(node)}</span>
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
  );
};
