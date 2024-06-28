import graphqlClient from "@/graphql/graphqlClientApollo";
import Content from "@/screens/layout/content";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { Badge } from "@/components/ui/badge";
import { constructPath } from "@/utils/fetch";
import { PROFILE_KIND } from "@/config/constants";
import { Link } from "react-router-dom";
import { useObjectItems } from "@/hooks/useObjectItems";
import { ObjectHelpButton } from "@/components/menu/object-help-button";
import useFilters from "@/hooks/useFilters";
import { Icon } from "@iconify-icon/react";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import { Skeleton } from "@/components/skeleton";

type ObjectHeaderProps = {
  schema: IModelSchema;
  objectId?: string;
};

const ObjectHeader = ({ schema, objectId }: ObjectHeaderProps) => {
  const [filters] = useFilters();

  const schemaKind = schema.kind as string;
  const { data: objectItemsData, loading: isCountLoading, error } = useObjectItems(schema, filters);

  const isProfile = schema.namespace === "Profile" || schemaKind === PROFILE_KIND;
  const breadcrumbModelLabel = isProfile ? "All Profiles" : schema.label || schema.name;

  return (
    <Content.Title
      title={
        <div className="text-md flex gap-2 items-center">
          <Link
            to={constructPath(`/objects/${isProfile ? PROFILE_KIND : schemaKind}`)}
            className="flex items-center cursor-pointer">
            <h1 className="font-semibold text-gray-900 mr-2 hover:underline">
              {breadcrumbModelLabel}
            </h1>
            <Badge>{isCountLoading && !error ? "..." : objectItemsData?.[schemaKind]?.count}</Badge>
          </Link>

          {objectId && <ObjectDetailBreadcrumb objectId={objectId} schema={schema} />}
        </div>
      }
      description={schema.description}
      isReloadLoading={isCountLoading}
      reload={() => graphqlClient.refetchQueries({ include: [schema.kind!] })}>
      <ObjectHelpButton
        kind={schema.kind}
        documentationUrl={schema.documentation}
        className="ml-auto"
      />
    </Content.Title>
  );
};

const ObjectDetailBreadcrumb = ({ schema, objectId }: ObjectHeaderProps & { objectId: string }) => {
  const { data, loading, error: objectDetailsError } = useObjectDetails(schema, objectId);

  if (objectDetailsError) return null;

  if (loading) {
    return (
      <>
        <Icon icon="mdi:chevron-right" />

        <Skeleton className="h-6 w-60" />
      </>
    );
  }

  const objectDetailsData = data[schema.kind!]?.edges[0]?.node;

  return (
    <>
      <Icon icon="mdi:chevron-right" />

      <p>{objectDetailsData.display_label}</p>
    </>
  );
};

export default ObjectHeader;
