import { GraphqlQueryActivities } from "@/entities/graphql/ui/graphql-query-activities";
import GraphqlQueryDetailsCard from "@/entities/graphql/ui/graphql-query-details-card";
import GraphQLQueryDetailsPageSkeleton from "@/entities/graphql/ui/graphql-query-details-page-skeleton";
import GraphqlQueryViewerCard from "@/entities/graphql/ui/graphql-query-viewer-card";
import { useObjectDetails } from "@/entities/nodes/hooks/useObjectDetails";
import { Permission } from "@/entities/permission/types";
import { ModelSchema } from "@/entities/schema/types";
import { CoreGraphQlQuery } from "@/shared/api/graphql/generated/graphql";
import NoDataFound from "@/shared/components/errors/no-data-found";

export function GraphqlQueryDetails({
  graphqlQueryId,
  graphqlQuerySchema,
  permission,
}: {
  graphqlQueryId: string;
  graphqlQuerySchema: ModelSchema;
  permission: Permission;
}) {
  const { loading, data, refetch } = useObjectDetails(graphqlQuerySchema, graphqlQueryId);

  if (loading) return <GraphQLQueryDetailsPageSkeleton />;

  const graphqlQueries = data && data.CoreGraphQLQuery.edges;
  if (graphqlQueries.length === 0) return <NoDataFound />;

  const graphqlQuery: CoreGraphQlQuery = graphqlQueries[0].node;

  return (
    <section className="grid grid-cols-1 lg:grid-cols-2 gap-2 p-2">
      <GraphqlQueryViewerCard query={graphqlQuery.query?.value ?? ""} />

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
}
