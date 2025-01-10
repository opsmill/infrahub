import { GRAPHQL_QUERY_OBJECT } from "@/config/constants";
import GraphqlQueryDetailsCard from "@/entities/graphql/details/graphql-query-details-card";
import GraphQLQueryDetailsPageSkeleton from "@/entities/graphql/details/graphql-query-details-page-skeleton";
import GraphqlQueryViewerCard from "@/entities/graphql/details/graphql-query-viewer-card";
import { getObjectDetailsPaginated } from "@/entities/nodes/api/getObjectDetails";
import { getSchemaObjectColumns } from "@/entities/nodes/object-items/getSchemaObjectColumns";
import { Permission } from "@/entities/permission/types";
import { getPermission } from "@/entities/permission/utils";
import { iNodeSchema, schemaState } from "@/entities/schema/schema.atom";
import { CoreGraphQlQuery } from "@/shared/api/graphql/generated/graphql";
import useQuery from "@/shared/api/graphql/useQuery";
import NoDataFound from "@/shared/components/errors/no-data-found";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { useTitle } from "@/shared/hooks/useTitle";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";

export default function GraphqlQueryDetailsPage({ graphqlQueryId }: { graphqlQueryId: string }) {
  useTitle("GraphQL Query details");

  const objectid = graphqlQueryId;

  const nodes = useAtomValue(schemaState);
  const graphqlQuerySchema = nodes.find((s) => s.kind === GRAPHQL_QUERY_OBJECT);

  const columns = getSchemaObjectColumns({ schema: graphqlQuerySchema });

  const query = gql(
    getObjectDetailsPaginated({
      objectid,
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
    graphqlQuery && (
      <GraphqlQueryDetailsContent
        graphqlQuerySchema={graphqlQuerySchema}
        graphqlQuery={graphqlQuery}
        refetch={refetch}
        permission={permission}
      />
    )
  );
}

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
