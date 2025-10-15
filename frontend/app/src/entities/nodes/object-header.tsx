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
import { NodeAttribute } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";

type ObjectHeaderProps = {
  schema: ModelSchema;
  objectId?: string;
};

const ObjectHeader = ({ schema, objectId }: ObjectHeaderProps) => {
  return objectId ? (
    <ObjectDetailsHeader schema={schema} objectId={objectId} />
  ) : (
    <ObjectItemsHeader schema={schema} />
  );
};

const ObjectItemsHeader = ({ schema }: ObjectHeaderProps) => {
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
};

const ObjectDetailsHeader = ({ schema, objectId }: ObjectHeaderProps & { objectId: string }) => {
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
};

export default ObjectHeader;
