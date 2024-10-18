import { ObjectHelpButton } from "@/components/menu/object-help-button";
import { GRAPHQL_QUERY_OBJECT } from "@/config/constants";
import { CoreGraphQlQuery } from "@/generated/graphql";
import { getObjectDetailsPaginated } from "@/graphql/queries/objects/getObjectDetails";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import NoDataFound from "@/screens/errors/no-data-found";
import GraphqlQueryDetailsCard from "@/screens/graphql/details/graphql-query-details-card";
import GraphQLQueryDetailsPageSkeleton from "@/screens/graphql/details/graphql-query-details-page-skeleton";
import GraphqlQueryViewerCard from "@/screens/graphql/details/graphql-query-viewer-card";
import Content from "@/screens/layout/content";
import { iNodeSchema, schemaState } from "@/state/atoms/schema.atom";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useParams } from "react-router-dom";

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
    })
  );

  const { loading, data, refetch } = useQuery(query, {
    skip: !graphqlQuerySchema,
  });

  if (!graphqlQuerySchema || loading) return <GraphQLQueryDetailsPageSkeleton />;

  const graphqlQueries = data && data.CoreGraphQLQuery.edges;
  if (graphqlQueries.length === 0) return <NoDataFound />;

  const graphqlQuery: CoreGraphQlQuery = graphqlQueries[0].node;

  return (
    <Content.Card>
      <Content.CardTitle
        title={graphqlQuery.display_label}
        badgeContent={graphqlQuerySchema.label}
        reload={() => refetch()}
        isReloadLoading={loading}
        end={
          <ObjectHelpButton
            className="ml-auto"
            documentationUrl={graphqlQuerySchema.documentation}
            kind={graphqlQuerySchema.kind}
          />
        }
      />

      {graphqlQuery && (
        <GraphqlQueryDetailsContent
          graphqlQuerySchema={graphqlQuerySchema}
          graphqlQuery={graphqlQuery}
          refetch={refetch}
        />
      )}
    </Content.Card>
  );
};

const GraphqlQueryDetailsContent = ({
  graphqlQuery,
  graphqlQuerySchema,
  refetch,
}: {
  graphqlQuery: CoreGraphQlQuery;
  graphqlQuerySchema: iNodeSchema;
  refetch: () => Promise<unknown>;
}) => {
  return (
    <section className="flex flex-wrap lg:flex-nowrap items-start gap-2 p-2">
      <GraphqlQueryDetailsCard data={graphqlQuery} schema={graphqlQuerySchema} refetch={refetch} />

      <GraphqlQueryViewerCard query={graphqlQuery.query.value ?? ""} />
    </section>
  );
};

export function Component() {
  return <GraphqlQueryDetailsPage />;
}
