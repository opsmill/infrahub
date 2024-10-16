import { ObjectHelpButton } from "@/components/menu/object-help-button";
import { GRAPHQL_QUERY_OBJECT } from "@/config/constants";
import { CoreGraphQlQuery } from "@/generated/graphql";
import { getObjectDetailsPaginated } from "@/graphql/queries/objects/getObjectDetails";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import NoDataFound from "@/screens/errors/no-data-found";
import UnauthorizedScreen from "@/screens/errors/unauthorized-screen";
import GraphqlQueryDetailsCard from "@/screens/graphql/details/graphql-query-details-card";
import GraphQLQueryDetailsPageSkeleton from "@/screens/graphql/details/graphql-query-details-page-skeleton";
import GraphqlQueryViewerCard from "@/screens/graphql/details/graphql-query-viewer-card";
import Content from "@/screens/layout/content";
import { getPermission } from "@/screens/permission/utils";
import { iNodeSchema, schemaState } from "@/state/atoms/schema.atom";
import { constructPath } from "@/utils/fetch";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { Link, useParams } from "react-router-dom";

const GraphqlQueryDetailsPage = () => {
  useTitle("GraphQL Query details");

  const { graphqlQueryId } = useParams();

  const nodes = useAtomValue(schemaState);
  const graphqlQuerySchema = nodes.find((s) => s.kind === GRAPHQL_QUERY_OBJECT);

  const columns = getSchemaObjectColumns({ schema: graphqlQuerySchema });

  const query = gql(
    getObjectDetailsPaginated({
      objectid: graphqlQueryId,
      kind: GRAPHQL_QUERY_OBJECT,
      columns,
      hasPermissions: true,
    })
  );

  const { loading, data, refetch } = useQuery(query, {
    skip: !graphqlQuerySchema,
  });

  if (!graphqlQuerySchema || loading) return <GraphQLQueryDetailsPageSkeleton />;

  const graphqlQueries = data && data.CoreGraphQLQuery.edges;
  if (graphqlQueries.length === 0) return <NoDataFound />;

  const graphqlQuery: CoreGraphQlQuery = graphqlQueries[0].node;

  const permission = getPermission(data?.[GRAPHQL_QUERY_OBJECT]?.permissions?.edges);

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  return (
    <Content>
      <Content.Title
        title={
          <div className="flex items-center gap-1">
            <Link
              to={constructPath(`/objects/${graphqlQuerySchema.kind}`)}
              className="hover:underline"
            >
              {graphqlQuerySchema.label}
            </Link>

            <Icon icon="mdi:chevron-right" className="text-2xl shrink-0 text-gray-400" />

            {loading ? (
              <span>...</span>
            ) : (
              <p className="max-w-2xl text-sm text-gray-500 font-normal">
                {graphqlQuery.display_label}
              </p>
            )}
          </div>
        }
        reload={() => refetch()}
        isReloadLoading={loading}
      >
        <ObjectHelpButton
          className="ml-auto"
          documentationUrl={graphqlQuerySchema.documentation}
          kind={graphqlQuerySchema.kind}
        />
      </Content.Title>

      {graphqlQuery && (
        <GraphqlQueryDetailsContent
          graphqlQuerySchema={graphqlQuerySchema}
          graphqlQuery={graphqlQuery}
          refetch={refetch}
          permission={permission}
        />
      )}
    </Content>
  );
};

const GraphqlQueryDetailsContent = ({
  graphqlQuery,
  graphqlQuerySchema,
  refetch,
  permission,
}: {
  graphqlQuery: CoreGraphQlQuery;
  graphqlQuerySchema: iNodeSchema;
  refetch: () => Promise<unknown>;
  permission: Permission;
}) => {
  return (
    <section className="flex flex-wrap lg:flex-nowrap items-start gap-2 p-2">
      <GraphqlQueryDetailsCard
        data={graphqlQuery}
        schema={graphqlQuerySchema}
        refetch={refetch}
        permission={permission}
      />

      <GraphqlQueryViewerCard query={graphqlQuery.query.value ?? ""} permission={permission} />
    </section>
  );
};

export function Component() {
  return <GraphqlQueryDetailsPage />;
}
