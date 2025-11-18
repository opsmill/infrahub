import { queryClient } from "@/shared/api/rest/client";
import { removeFiltersNotInSchema } from "@/shared/components/filters/utils/remove-filters-not-in-schema";
import Content from "@/shared/components/layout/content";
import { ObjectDetailsButton } from "@/shared/components/menu/object-details-button";
import { ObjectHelpButton } from "@/shared/components/menu/object-help-button";
import { Skeleton } from "@/shared/components/skeleton";
import useFilters from "@/shared/hooks/useFilters";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { useObjectsCount } from "@/entities/nodes/object/domain/get-objects-count.query";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import type { NodeAttribute } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

interface ObjectItemsHeaderProps {
  schema: ModelSchema;
}

export function ObjectItemsHeader({ schema }: ObjectItemsHeaderProps) {
  const [filters] = useFilters();
  const {
    data: count,
    isPending,
    isRefetching,
    isError,
  } = useObjectsCount({
    objectKind: schema.kind as string,
    filters: removeFiltersNotInSchema(filters, schema),
  });

  const refetchObjects = async () => {
    await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
  };

  return (
    <Content.CardTitle
      title={schema.label || schema.name}
      badgeContent={isPending && !isError ? "..." : count}
      description={schema.description}
      isReloadLoading={isRefetching}
      reload={refetchObjects}
      data-testid="object-header"
      end={
        <ObjectHelpButton
          kind={schema.kind}
          documentationUrl={schema.documentation}
          className="ml-auto"
        />
      }
    />
  );
}

interface ObjectDetailsHeaderProps extends ObjectItemsHeaderProps {
  objectId: string;
}

export function ObjectDetailsHeader({ schema, objectId }: ObjectDetailsHeaderProps) {
  const {
    data: objectDetailsData,
    isPending,
    isRefetching,
    error,
  } = useGetObject({ objectSchema: schema, objectId });

  if (error) return null;

  const title = isPending ? (
    <Skeleton className="h-6 w-60" />
  ) : (
    <div className="flex items-center gap-3">
      {objectDetailsData?.display_label ?? `${schema.label} not found`}

      <ObjectDetailsButton
        id={objectId}
        objectKind={schema.kind!}
        data-testid="object-details-button"
        hfid={objectDetailsData?.hfid && JSON.stringify(objectDetailsData?.hfid)}
      />
    </div>
  );

  return (
    <Content.CardTitle
      title={title}
      description={
        (objectDetailsData?.description as NodeAttribute | undefined)?.value ?? schema.description
      }
      isReloadLoading={isRefetching}
      reload={async () => {
        await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
      }}
      end={
        <ObjectHelpButton
          kind={schema.kind}
          documentationUrl={schema.documentation}
          className="ml-auto"
        />
      }
      data-testid="object-header"
    />
  );
}
