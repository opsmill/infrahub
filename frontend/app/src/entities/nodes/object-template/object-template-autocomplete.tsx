import React from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import {
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxListProps,
} from "@/shared/components/ui/combobox";
import { Spinner } from "@/shared/components/ui/spinner";
import { debounce } from "@/shared/utils/common";

import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { NodeObject } from "@/entities/nodes/types";
import { TemplateSchema } from "@/entities/schema/types";

export interface ObjectTemplateAutocompleteProps extends Omit<ComboboxListProps, "onSelect"> {
  templateSchema: TemplateSchema;
  onSelect: (node: NodeObject) => void;
}

export function ObjectTemplateAutocomplete({
  templateSchema,
  onSelect,
  ...props
}: ObjectTemplateAutocompleteProps) {
  const [search, setSearch] = React.useState("");
  const { data, isPending, error, hasNextPage, fetchNextPage, isFetchingNextPage } = useObjects({
    schema: templateSchema,
    filters: search ? [{ name: "any__value", value: search }] : undefined,
    getAttributesVisible: (attributes) => attributes,
    getRelationshipsVisible: (relationships) => relationships,
  });

  if (error) return <ErrorScreen message={error.message} />;

  const setSearchDebounced = debounce(setSearch, 300);

  return (
    <ComboboxList
      onValueChange={(newValue) => setSearchDebounced(newValue)}
      shouldFilter={false}
      {...props}
    >
      {isPending ? (
        <Spinner className="flex justify-center m-2" />
      ) : (
        <>
          <ComboboxEmpty>No template found</ComboboxEmpty>

          {data.pages.map((page) => {
            return page.map((node) => {
              return (
                <ComboboxItem key={node.id} value={node.id} onSelect={() => onSelect(node)}>
                  <span className="truncate">{getNodeLabel(node)}</span>
                </ComboboxItem>
              );
            });
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
