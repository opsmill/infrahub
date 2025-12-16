import type { CoreGraphQlQuery } from "@/shared/api/graphql/generated/graphql";
import ErrorScreen from "@/shared/components/errors/error-screen";

import { GraphqlQueryActivities } from "@/entities/graphql/ui/graphql-query-activities";
import GraphqlQueryDetailsCard from "@/entities/graphql/ui/graphql-query-details-card";
import GraphQLQueryDetailsPageSkeleton from "@/entities/graphql/ui/graphql-query-details-page-skeleton";
import GraphqlQueryViewerCard from "@/entities/graphql/ui/graphql-query-viewer-card";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

export function GraphqlQueryDetails({
  graphqlQueryId,
  graphqlQuerySchema,
  permission,
}: {
  graphqlQueryId: string;
  graphqlQuerySchema: ModelSchema;
  permission: Permission;
}) {
  const { isPending, error, data } = useGetObject({
    objectSchema: graphqlQuerySchema,
    objectId: graphqlQueryId,
  });

  if (isPending) {
    return <GraphQLQueryDetailsPageSkeleton />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const graphqlQuery: CoreGraphQlQuery = data as unknown as CoreGraphQlQuery;

  return (
    <section className="grid grid-cols-1 gap-2 p-2 lg:grid-cols-2">
      <GraphqlQueryViewerCard query={graphqlQuery.query?.value ?? ""} />

      <div className="flex flex-col gap-2">
        <GraphqlQueryDetailsCard
          data={graphqlQuery}
          schema={graphqlQuerySchema}
          permission={permission}
        />

        <GraphqlQueryActivities id={graphqlQueryId} />
      </div>
    </section>
  );
}
