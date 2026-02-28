import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { GRAPHQL_QUERY_OBJECT } from "@/shared/config/constants";

import GraphqlQueryDetailsCard from "@/entities/graphql/ui/graphql-query-details-card";
import GraphQLQueryDetailsPageSkeleton from "@/entities/graphql/ui/graphql-query-details-page-skeleton";
import { GraphqlQueryViewerCard } from "@/entities/graphql/ui/graphql-query-viewer-card";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { ObjectActivitiesCard } from "@/entities/nodes/object/ui/object-details/object-activities-card";
import type { NodeAttributeWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

interface GraphqlQueryDetailsProps {
  graphqlQueryId: string;
  graphqlQuerySchema: ModelSchema;
  permission: Permission;
}

export function GraphqlQueryDetails({
  graphqlQueryId,
  graphqlQuerySchema,
  permission,
}: GraphqlQueryDetailsProps) {
  const {
    isPending,
    error,
    data: graphqlQuery,
  } = useGetObject({
    objectSchema: graphqlQuerySchema,
    objectId: graphqlQueryId,
  });

  if (isPending) {
    return <GraphQLQueryDetailsPageSkeleton />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return (
    <section className="grid grid-cols-1 items-start gap-2 p-2 lg:grid-cols-2">
      <GraphqlQueryViewerCard
        query={(graphqlQuery.query as NodeAttributeWithMetadata).value as string}
      />

      <Col>
        <GraphqlQueryDetailsCard
          data={graphqlQuery}
          schema={graphqlQuerySchema}
          permission={permission}
        />

        <ObjectActivitiesCard objectKind={GRAPHQL_QUERY_OBJECT} objectId={graphqlQueryId} />
      </Col>
    </section>
  );
}
