import { Navigate, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { GRAPHQL_QUERY_OBJECT, MENU_EXCLUDELIST } from "@/shared/config/constants";

import { GraphqlQueryDetails } from "@/entities/nodes/object/ui/CoreGraphQLQuery/graphql-query-details";
import { ObjectDetailsBody } from "@/entities/nodes/object/ui/object-details/object-details-body";
import { ObjectDetailsHeader } from "@/entities/nodes/object/ui/object-details/object-details-header";
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

  if (MENU_EXCLUDELIST.includes(schema.kind!)) {
    return <Navigate to={constructPath("/")} />;
  }

  return (
    <Content.Card className="flex grow flex-col">
      <RequireObjectPermissions schema={schema} loadingClassName="h-full">
        {({ permission }) => (
          <>
            <ObjectDetailsHeader
              objectSchema={schema}
              objectId={objectId}
              permission={permission}
            />

            {objectKind === GRAPHQL_QUERY_OBJECT ? (
              <GraphqlQueryDetails
                graphqlQuerySchema={schema}
                graphqlQueryId={objectId}
                permission={permission}
              />
            ) : (
              <ObjectDetailsBody
                objectSchema={schema}
                objectId={objectId}
                permission={permission}
              />
            )}
          </>
        )}
      </RequireObjectPermissions>
    </Content.Card>
  );
}

export const Component = ObjectDetailsPage;
