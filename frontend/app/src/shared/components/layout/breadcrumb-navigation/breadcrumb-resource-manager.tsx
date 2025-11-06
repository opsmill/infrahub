import { Icon } from "@iconify-icon/react";
import { keepPreviousData } from "@tanstack/react-query";
import React from "react";
import { Collection, ListLayout, Virtualizer } from "react-aria-components";
import { useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Autocomplete } from "@/shared/components/aria/autocomplete";
import { ListBox, ListBoxItem, ListBoxLoadMoreItem } from "@/shared/components/aria/list-box";
import { MenuTrigger } from "@/shared/components/aria/menu";
import { Popover } from "@/shared/components/aria/popover";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { BreadcrumbItemTrigger } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-trigger";
import {
  Breadcrumb,
  BreadcrumbError,
  BreadcrumbItem,
  BreadcrumbLoading,
} from "@/shared/components/ui/breadcrumb";
import { debounce } from "@/shared/utils/common";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { useRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships.query";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

export function BreadcrumbResourceManager() {
  const { resourcePoolId, resourceId } = useParams();

  return (
    <Breadcrumb data-testid="breadcrumb-resource-manager">
      <BreadcrumbItem href={constructPath("/resource-manager")}>Resource manager</BreadcrumbItem>
      {resourcePoolId && <ResourcePoolSelector resourcePoolId={resourcePoolId} />}
      {resourceId && resourcePoolId && (
        <ResourceSelector resourceId={resourceId} resourcePoolId={resourcePoolId} />
      )}
    </Breadcrumb>
  );
}

function ResourcePoolSelector({ resourcePoolId }: { resourcePoolId: string }) {
  const { schema } = useSchema(RESOURCE_GENERIC_KIND);
  const { data, isPending, error } = useGetObject(
    {
      objectSchema: schema!,
      objectId: resourcePoolId,
    },
    {
      placeholderData: keepPreviousData,
      enabled: !!schema,
    }
  );

  if (isPending || !schema) {
    return <BreadcrumbLoading />;
  }

  if (error) {
    return <BreadcrumbError error={error} />;
  }

  return (
    <MenuTrigger>
      <BreadcrumbItemTrigger>{data.display_label}</BreadcrumbItemTrigger>

      <Popover className="bg-stone-100/50 backdrop-blur">
        <ResourcePoolAutocomplete />
      </Popover>
    </MenuTrigger>
  );
}

function ResourcePoolAutocomplete() {
  const [search, setSearch] = React.useState("");
  const setSearchDebounced = debounce(setSearch, 300);
  const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useRelationships({ peer: RESOURCE_GENERIC_KIND, search });

  if (error) return <ErrorScreen message={error.message} />;

  const flatData = data?.pages.flat() ?? [];

  return (
    <Autocomplete onInputChange={setSearchDebounced}>
      <ListBox className="max-h-58">
        <Collection items={flatData}>
          {({ id, display_label, __typename }) => {
            const { schema } = getSchema(__typename);

            return (
              <ListBoxItem
                textValue={display_label}
                href={constructPath(`/resource-manager/${id}`)}
              >
                <Icon icon={getSchemaIcon(schema)} />
                <span className="truncate">{display_label}</span>
              </ListBoxItem>
            );
          }}
        </Collection>

        {(isPending || hasNextPage) && (
          <ListBoxLoadMoreItem
            isLoading={isPending || isFetchingNextPage}
            onLoadMore={fetchNextPage}
          />
        )}
      </ListBox>
    </Autocomplete>
  );
}

function ResourceSelector({
  resourceId,
  resourcePoolId,
}: {
  resourceId: string;
  resourcePoolId: string;
}) {
  const { schema: poolSchema } = useSchema(RESOURCE_GENERIC_KIND);

  // Find the resources relationship to get the peer kind
  const resourcesRelationship = poolSchema?.relationships?.find((rel) => rel.name === "resources");
  const resourceKind = resourcesRelationship?.peer;

  const { schema: resourceSchema } = useSchema(resourceKind);
  const { data, isPending, error } = useGetObject(
    {
      objectSchema: resourceSchema!,
      objectId: resourceId,
    },
    {
      placeholderData: keepPreviousData,
      enabled: !!resourceSchema,
    }
  );

  if (isPending || !resourceSchema) {
    return <BreadcrumbLoading />;
  }

  if (error) {
    return <BreadcrumbError error={error} />;
  }

  return (
    <MenuTrigger>
      <BreadcrumbItemTrigger>{data.display_label}</BreadcrumbItemTrigger>

      <Popover className="bg-stone-100/50 backdrop-blur">
        <ResourceAutocomplete
          resourcePoolId={resourcePoolId}
          resourceKind={resourceKind}
          resourcesRelationship={resourcesRelationship?.name ?? "resources"}
        />
      </Popover>
    </MenuTrigger>
  );
}

function ResourceAutocomplete({
  resourcePoolId,
  resourceKind,
  resourcesRelationship,
}: {
  resourcePoolId: string;
  resourceKind: string;
  resourcesRelationship: string;
}) {
  const [search, setSearch] = React.useState("");
  const setSearchDebounced = debounce(setSearch, 300);

  // Filter to only show resources that belong to this pool
  const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useRelationships({
      peer: resourceKind,
      search,
      filterQuery: {
        [`${resourcesRelationship}__ids`]: [resourcePoolId],
      },
    });

  if (error) return <ErrorScreen message={error.message} />;

  const flatData = data?.pages.flat() ?? [];

  return (
    <Autocomplete onInputChange={setSearchDebounced}>
      <Virtualizer
        layout={ListLayout}
        layoutOptions={{ rowHeight: 30, loaderHeight: 30, padding: 4 }}
      >
        <ListBox className="max-h-58">
          <Collection items={flatData}>
            {({ id, display_label, __typename }) => {
              const { schema } = getSchema(__typename);

              return (
                <ListBoxItem
                  textValue={display_label}
                  href={constructPath(`/resource-manager/${resourcePoolId}/resources/${id}`)}
                >
                  <Icon icon={getSchemaIcon(schema)} />
                  <span className="truncate">{display_label}</span>
                </ListBoxItem>
              );
            }}
          </Collection>

          {(isPending || hasNextPage) && (
            <ListBoxLoadMoreItem
              isLoading={isPending || isFetchingNextPage}
              onLoadMore={fetchNextPage}
            />
          )}
        </ListBox>
      </Virtualizer>
    </Autocomplete>
  );
}
