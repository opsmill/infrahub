import { ObjectHelpButton } from "@/components/menu/object-help-button";
import { Skeleton } from "@/components/skeleton";
import graphqlClient from "@/graphql/graphqlClientApollo";
import useFilters from "@/hooks/useFilters";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import { useObjectItems } from "@/hooks/useObjectItems";
import Content from "@/screens/layout/content";
import { getPermission } from "@/screens/permission/utils";
import { IModelSchema } from "@/state/atoms/schema.atom";

type ObjectHeaderProps = {
  schema: IModelSchema;
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
  const kindFilter = filters?.find((filter) => filter.name == "kind__value");

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

  return (
    <Content.CardTitle
      title={
        loading ? (
          <Skeleton className="h-6 w-60" />
        ) : (
          (objectDetailsData?.display_label ?? `${schema.label} not found`)
        )
      }
      description={schema.description}
      isReloadLoading={loading}
      reload={() => graphqlClient.refetchQueries({ include: [schema.kind!] })}
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
