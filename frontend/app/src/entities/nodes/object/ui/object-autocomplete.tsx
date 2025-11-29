import { Icon } from "@iconify-icon/react";
import React from "react";
import { Collection, ListLayout, Virtualizer } from "react-aria-components";

import { Autocomplete } from "@/shared/components/aria/autocomplete";
import { ListBox, ListBoxItem, ListBoxLoadMoreItem } from "@/shared/components/aria/list-box";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { debounce } from "@/shared/utils/common";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { GetRelationshipsParams } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import { useRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships.query";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

interface ObjectAutocompleteProps {
  objectKind: string;
  filterQuery?: GetRelationshipsParams["filterQuery"];
  className?: string;
}

export function ObjectAutocomplete({
  objectKind,
  filterQuery,
  className,
}: ObjectAutocompleteProps) {
  const [search, setSearch] = React.useState("");
  const setSearchDebounced = debounce(setSearch, 300);
  const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useRelationships({ peer: objectKind, search, filterQuery });

  if (isPending) {
    return (
      <Autocomplete onInputChange={setSearchDebounced}>
        <ListBox className="p-1">
          <ListBoxLoadMoreItem isLoading />
        </ListBox>
      </Autocomplete>
    );
  }

  if (error) return <ErrorScreen message={error.message} />;

  const flatData = data?.pages.flat() ?? [];

  return (
    <Autocomplete onInputChange={setSearchDebounced}>
      <Virtualizer
        layout={ListLayout}
        layoutOptions={{ rowHeight: 30, loaderHeight: 30, padding: 4 }}
      >
        <ListBox className={className} emptyMessage="No result found">
          <Collection items={flatData}>
            {(node) => {
              const { schema } = getSchema(node.__typename);
              const nodeLabel = getNodeLabel(node);

              return (
                <ListBoxItem
                  textValue={nodeLabel}
                  href={getObjectDetailsUrl(node.__typename, node.id)}
                >
                  <Icon icon={getSchemaIcon(schema)} />
                  <span className="truncate">{nodeLabel}</span>
                </ListBoxItem>
              );
            }}
          </Collection>

          {hasNextPage && (
            <ListBoxLoadMoreItem isLoading={isFetchingNextPage} onLoadMore={fetchNextPage} />
          )}
        </ListBox>
      </Virtualizer>
    </Autocomplete>
  );
}
