import React, { forwardRef } from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import {
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  type ComboboxListProps,
} from "@/shared/components/ui/combobox";
import { Spinner } from "@/shared/components/ui/spinner";
import { debounce } from "@/shared/utils/common";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { useRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships.query";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface RelationshipComboboxListProps
  extends Omit<ComboboxListProps, "value" | "onSelect"> {
  peer: string;
  onSelect: (value: RelationshipNode) => void;
  value?: RelationshipNode | null;
  filterItem?: (relationshipNode: RelationshipNode) => boolean;
  filterQuery?: Record<string, string | number | boolean | string[]>;
}

export const RelationshipComboboxList = forwardRef<HTMLDivElement, RelationshipComboboxListProps>(
  ({ peer, value, onSelect, filterItem, filterQuery, ...props }, ref) => {
    const [search, setSearch] = React.useState("");
    const { schema } = useSchema(peer);
    const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
      useRelationships({ peer, search, filterQuery });

    if (error) return <ErrorScreen message={error.message} />;

    const setSearchDebounced = debounce(setSearch, 300);

    return (
      <ComboboxList
        ref={ref}
        onValueChange={(newValue) => setSearchDebounced(newValue)}
        shouldFilter={false}
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
  }
);
