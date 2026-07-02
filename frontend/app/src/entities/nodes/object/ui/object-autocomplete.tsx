import { Icon } from "@iconify-icon/react";
import { Autocomplete, ListBox, ListBoxItem, ListBoxLoadMoreItem } from "@infrahub/ui";
import React from "react";
import { Collection } from "react-aria-components";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { debounce } from "@/shared/utils/common";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { GetRelationshipsParams } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import { useRelationships } from "@/entities/nodes/relationships/ui/queries/get-relationships.query";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

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
        <ListBox>
          <ListBoxLoadMoreItem isLoading />
        </ListBox>
      </Autocomplete>
    );
  }

  if (error) return <ErrorScreen message={error.message} />;

  const flatData = data?.pages.flat() ?? [];

  return (
    <Autocomplete onInputChange={setSearchDebounced}>
      <ListBox virtualized className={className} emptyMessage="No result found">
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
    </Autocomplete>
  );
}
