import graphqlClient from "@/graphql/graphqlClientApollo";
import Content from "@/screens/layout/content";
import { useState } from "react";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { Badge } from "@/components/ui/badge";
import { constructPath } from "@/utils/fetch";
import { PROFILE_KIND } from "@/config/constants";
import { Link } from "react-router-dom";
import { useObjectItems } from "@/hooks/useObjectItems";
import { ObjectHelpButton } from "@/components/menu/object-help-button";

type ObjectHeaderProps = {
  schema: IModelSchema;
};

const ObjectHeader = ({ schema }: ObjectHeaderProps) => {
  const [isReloadLoading, setIsReloadLoading] = useState(false);

  const schemaKind = schema.kind as string;
  const { data, loading: isCountLoading, error } = useObjectItems(schema);

  const isProfile = schema.namespace === "Profile" || schemaKind === PROFILE_KIND;
  const breadcrumbModelLabel = isProfile ? "All Profiles" : schema.label || schema.name;

  return (
    <Content.Title
      title={
        <Link
          to={constructPath(`/objects/${isProfile ? PROFILE_KIND : schemaKind}`)}
          className="flex items-center">
          <h1 className="text-md font-semibold text-gray-900 mr-2">{breadcrumbModelLabel}</h1>
          <Badge>{isCountLoading && !error ? "..." : data?.[schemaKind]?.count}</Badge>
        </Link>
      }
      description={schema.description}
      isReloadLoading={isReloadLoading}
      reload={() => {
        setIsReloadLoading(true);
        graphqlClient.reFetchObservableQueries().then(() => setIsReloadLoading(false));
      }}>
      <ObjectHelpButton
        kind={schema.kind}
        documentationUrl={schema.documentation}
        className="ml-auto"
      />
    </Content.Title>
  );
};

export default ObjectHeader;
