import { useParams } from "react-router-dom";
import { useTitle } from "../../../hooks/useTitle";
import useQuery from "../../../hooks/useQuery";
import { CoreGraphQlQuery } from "../../../generated/graphql";
import { useAtomValue } from "jotai/index";
import { schemaState } from "../../../state/atoms/schema.atom";
import { GRAPHQL_QUERY_OBJECT } from "../../../config/constants";
import GraphQLQueryDetailsPageSkeleton from "./graphql-query-details-page-skeleton";
import { getSchemaObjectColumns } from "../../../utils/getSchemaObjectColumns";
import { gql } from "@apollo/client";
import { getObjectDetailsPaginated } from "../../../graphql/queries/objects/getObjectDetails";

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

  const { loading, data } = useQuery(query, {
    skip: !graphqlQuerySchema,
  });

  if (!graphqlQuerySchema || loading) return <GraphQLQueryDetailsPageSkeleton />;

  const graphqlQuery: CoreGraphQlQuery = data && data.CoreGraphQLQuery.edges[0].node;

  return JSON.stringify(graphqlQuery);
};

export default GraphqlQueryDetailsPage;
