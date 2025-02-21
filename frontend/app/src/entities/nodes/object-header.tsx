import { useObjectDetails } from "@/entities/nodes/hooks/useObjectDetails";
import { useObjectItems } from "@/entities/nodes/hooks/useObjectItems";
import { getPermission } from "@/entities/permission/utils";
import { ModelSchema } from "@/entities/schema/types";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { queryClient } from "@/shared/api/rest/client";
import Content from "@/shared/components/layout/content";
import { ObjectDetailsButton } from "@/shared/components/menu/object-details-button";
import { ObjectHelpButton } from "@/shared/components/menu/object-help-button";
import { Skeleton } from "@/shared/components/skeleton";
import useFilters from "@/shared/hooks/useFilters";

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
  const { data, loading, error } = useObjectItems(schema, filters);
  const kindFilter = filters?.find((filter) => filter.name === "kind__value");

  const schemaKind = kindFilter?.value || (schema.kind as string);
  const { count, permissions } = data?.[schemaKind] ?? { count: undefined, permissions: undefined };
  const currentPermission = getPermission(permissions?.edges);

  if (!currentPermission.view.isAllowed) {
    return null;
  }

  return (
    <Content.CardTitle
      title={schema.label || schema.name}
      badgeContent={loading && !error ? "..." : count}
      description={schema.description}
      isReloadLoading={loading}
      reload={() => graphqlClient.refetchQueries({ include: [schema.kind!] })}
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
  const { data, loading, error } = useObjectDetails(schema, objectId);

  if (error) return null;

  const objectDetailsData = data?.[schema.kind!]?.edges[0]?.node;

  const title = loading ? (
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
      description={objectDetailsData?.description?.value ?? schema.description}
      isReloadLoading={loading}
      reload={() => {
        graphqlClient.refetchQueries({ include: [schema.kind!] });
        queryClient.invalidateQueries({ queryKey: ["events", [objectId]] });
      }}
      end={
        objectDetailsData?.hfid &&
        objectId && (
          <ObjectHelpButton
            kind={schema.kind}
            documentationUrl={schema.documentation}
            className="ml-auto"
          />
        )
      }
      data-testid="object-header"
    />
  );
};

export default ObjectHeader;
