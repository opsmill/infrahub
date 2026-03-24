import { queryClient } from "@/shared/api/rest/client";
import { removeFiltersNotInSchema } from "@/shared/components/filters/utils/remove-filters-not-in-schema";
import Content from "@/shared/components/layout/content";
import useFilters from "@/shared/hooks/useFilters";

import { useObjectsCount } from "@/entities/nodes/object/domain/get-objects-count.query";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
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
    objectKind: schema.kind!,
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
