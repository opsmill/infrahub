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
import { Permission } from "@/screens/permission/types";
import { getPermission } from "@/screens/permission/utils";
import { iNodeSchema, schemaState } from "@/state/atoms/schema.atom";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useParams } from "react-router-dom";

export default function GraphqlQueryDetailsPage() {
  useTitle("GraphQL Query details");

  const { objectid } = useParams();

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
