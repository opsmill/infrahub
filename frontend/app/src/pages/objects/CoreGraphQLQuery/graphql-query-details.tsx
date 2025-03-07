import { GRAPHQL_QUERY_OBJECT } from "@/config/constants";
import { GraphqlQueryActivities } from "@/entities/graphql/ui/graphql-query-activities";
import GraphqlQueryDetailsCard from "@/entities/graphql/ui/graphql-query-details-card";
import GraphQLQueryDetailsPageSkeleton from "@/entities/graphql/ui/graphql-query-details-page-skeleton";
import GraphqlQueryViewerCard from "@/entities/graphql/ui/graphql-query-viewer-card";
import { useObjectDetails } from "@/entities/nodes/hooks/useObjectDetails";
import { useGetObjectPermissions } from "@/entities/permission/domain/get-object-permissions.query";
import { Permission } from "@/entities/permission/types";
import { ModelSchema, NodeSchema } from "@/entities/schema/types";
import { CoreGraphQlQuery } from "@/shared/api/graphql/generated/graphql";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { useTitle } from "@/shared/hooks/useTitle";

export interface GraphqlQueryDetailsPageProps {
  graphqlQuerySchema: ModelSchema;
  graphqlQueryId: string;
}

export default function GraphqlQueryDetailsPage({
  graphqlQuerySchema,
  graphqlQueryId,
}: GraphqlQueryDetailsPageProps) {
  useTitle("GraphQL Query details");

  const { isPending, error, data: permission } = useGetObjectPermissions(GRAPHQL_QUERY_OBJECT);

  if (isPending) {
    return <LoadingIndicator className="h-[calc(100vh-10rem)]" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching permissions." />;
  }

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  return (
    <GraphqlQueryDetails
      graphqlQueryId={graphqlQueryId}
      graphqlQuerySchema={graphqlQuerySchema as NodeSchema}
      permission={permission}
    />
  );
}

const GraphqlQueryDetails = ({
  graphqlQueryId,
  graphqlQuerySchema,
  permission,
}: {
  graphqlQueryId: string;
  graphqlQuerySchema: NodeSchema;
  permission: Permission;
}) => {
  const { loading, data, refetch } = useObjectDetails(graphqlQuerySchema, graphqlQueryId);

  if (loading) return <GraphQLQueryDetailsPageSkeleton />;

  const graphqlQueries = data && data.CoreGraphQLQuery.edges;
  if (graphqlQueries.length === 0) return <NoDataFound />;

  const graphqlQuery: CoreGraphQlQuery = graphqlQueries[0].node;

  return (
    <section className="grid grid-cols-2 gap-2 p-2">
      <GraphqlQueryViewerCard query={graphqlQuery.query.value ?? ""} />

      <div className="flex flex-col gap-2">
        <GraphqlQueryDetailsCard
          data={graphqlQuery}
          schema={graphqlQuerySchema}
          refetch={refetch}
          permission={permission}
        />

        <GraphqlQueryActivities id={graphqlQueryId} />
      </div>
    </section>
  );
};
