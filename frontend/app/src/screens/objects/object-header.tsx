import { ObjectHelpButton } from "@/components/menu/object-help-button";
import { Skeleton } from "@/components/skeleton";
import { Badge } from "@/components/ui/badge";
import { PROFILE_KIND } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import useFilters from "@/hooks/useFilters";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import { useObjectItems } from "@/hooks/useObjectItems";
import Content from "@/screens/layout/content";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { constructPath } from "@/utils/fetch";
import { getPermission } from "@/utils/permissions";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";

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
  const isProfile = schema.namespace === "Profile" || schemaKind === PROFILE_KIND;
  const breadcrumbModelLabel = isProfile ? "All Profiles" : schema.label || schema.name;
  const { count, permissions } = data ? data[schemaKind] : {};
  const currentPermission = getPermission(permissions?.edges);

  if (!currentPermission.view.isAllowed) {
    return null;
  }

  return (
    <Content.Title
      title={
        <div className="text-md flex gap-2 items-center">
          <Link
            to={constructPath(`/objects/${isProfile ? PROFILE_KIND : schemaKind}`)}
            className="flex items-center cursor-pointer"
          >
            <h1 className="font-semibold text-gray-900 mr-2 hover:underline">
              {breadcrumbModelLabel}
            </h1>
            <Badge>{loading && !error ? "..." : count}</Badge>
          </Link>
        </div>
      }
      description={schema.description}
      isReloadLoading={loading}
      reload={() => graphqlClient.refetchQueries({ include: [schema.kind!] })}
      data-testid="object-header"
    >
      <ObjectHelpButton
        kind={schema.kind}
        documentationUrl={schema.documentation}
        className="ml-auto"
      />
    </Content.Title>
  );
};

const ObjectDetailsHeader = ({ schema, objectId }: ObjectHeaderProps & { objectId: string }) => {
  const { data, loading, error } = useObjectDetails(schema, objectId);

  if (error) return null;

  const schemaKind = schema.kind as string;
  const isProfile = schema.namespace === "Profile" || schemaKind === PROFILE_KIND;
  const breadcrumbModelLabel = isProfile ? "All Profiles" : schema.label || schema.name;

  const objectDetailsData = data?.[schema.kind!]?.edges[0]?.node;

  return (
    <Content.Title
      title={
        <div className="text-md flex gap-2 items-center">
          <Link
            to={constructPath(`/objects/${isProfile ? PROFILE_KIND : schemaKind}`)}
            className="flex items-center cursor-pointer"
          >
            <h1 className="font-semibold text-gray-900 hover:underline">{breadcrumbModelLabel}</h1>
          </Link>

          {loading ? (
            <>
              <Icon icon="mdi:chevron-right" />
              <Skeleton className="h-6 w-60" />
            </>
          ) : (
            <>
              <Icon icon="mdi:chevron-right" />
              <p>{objectDetailsData?.display_label ?? "not found"}</p>
            </>
          )}
        </div>
      }
      description={schema.description}
      isReloadLoading={loading}
      reload={() => graphqlClient.refetchQueries({ include: [schema.kind!] })}
      data-testid="object-header"
    >
      <ObjectHelpButton
        kind={schema.kind}
        documentationUrl={schema.documentation}
        className="ml-auto"
      />
    </Content.Title>
  );
};

export default ObjectHeader;
