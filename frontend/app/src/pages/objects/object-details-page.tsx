import { Navigate, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { GRAPHQL_QUERY_OBJECT } from "@/shared/config/constants";

import { GraphqlQueryDetails } from "@/entities/nodes/object/ui/CoreGraphQLQuery/graphql-query-details";
import { ObjectDetails } from "@/entities/nodes/object/ui/object-details";
import { ObjectDetailsHeader } from "@/entities/nodes/object-header";
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
    <Content.Card className="flex flex-col">
      <RequireObjectPermissions
        objectKind={schema.kind as string}
        loadingClassName="h-[calc(100vh-10.5rem)]"
      >
        {({ permission }) => (
          <>
            <ObjectDetailsHeader schema={schema} objectId={objectId} />

            {objectKind === GRAPHQL_QUERY_OBJECT ? (
              <GraphqlQueryDetails
                graphqlQuerySchema={schema}
                graphqlQueryId={objectId}
                permission={permission}
              />
            ) : (
              <ObjectDetails objectSchema={schema} objectId={objectId} permission={permission} />
            )}
          </>
        )}
      </RequireObjectPermissions>
    </Content.Card>
  );
}

export const Component = ObjectDetailsPage;
