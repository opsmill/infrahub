import { Navigate, useParams } from "react-router";

import { GRAPHQL_QUERY_OBJECT } from "@/config/constants";

import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";

import { GraphqlQueryDetails } from "@/entities/nodes/object/ui/CoreGraphQLQuery/graphql-query-details";
import { ObjectDetails } from "@/entities/nodes/object/ui/object-details";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

function ObjectDetailsPage() {
  const { objectKind, objectId } = useParams();
  const { schema } = useSchema(objectKind);

  if (!schema) {
    return <ErrorScreen message={`Schema ${objectKind} not found.`} />;
  }

  if (!objectId) {
    return <Navigate to={constructPath(`/objects/${objectKind}`)} />;
  }

  return (
    <RequireObjectPermissions
      objectKind={schema.kind as string}
      loadingClassName="h-[calc(100vh-10.5rem)]"
    >
      {({ permission }) => {
        if (objectKind === GRAPHQL_QUERY_OBJECT) {
          return (
            <GraphqlQueryDetails
              graphqlQuerySchema={schema}
              graphqlQueryId={objectId}
              permission={permission}
            />
          );
        }

        return <ObjectDetails objectSchema={schema} objectId={objectId} permission={permission} />;
      }}
    </RequireObjectPermissions>
  );
}

export const Component = ObjectDetailsPage;
