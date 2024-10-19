import { Card } from "@/components/ui/card";
import { ARTIFACT_OBJECT, GRAPHQL_QUERY_OBJECT, TASK_OBJECT } from "@/config/constants";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import ArtifactsDetails from "@/screens/artifacts/object-item-details-paginated";
import ErrorScreen from "@/screens/errors/error-screen";
import NoDataFound from "@/screens/errors/no-data-found";
import UnauthorizedScreen from "@/screens/errors/unauthorized-screen";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import ObjectItemDetails from "@/screens/object-item-details/object-item-details-paginated";
import ObjectItems from "@/screens/object-items/object-items-paginated";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { NetworkStatus } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";
import GraphqlQueryDetailsPage from "./CoreGraphQLQuery/graphql-query-details";

export function ObjectDetailsPage() {
  const { objectKind, objectid } = useParams();

  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const schema = [...nodes, ...generics, ...profiles].find(({ kind }) => kind === objectKind);

  if (!schema) return <ErrorScreen message={`Object ${objectKind} not found.`} />;

  if (!objectid) return <ObjectItems schema={schema} />;

  const { data, networkStatus, error, permission } = useObjectDetails(schema, objectid);

  if (networkStatus === NetworkStatus.loading) {
    return <LoadingScreen />;
  }

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  if (error) {
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="Something went wrong when fetching the object details." />;
  }

  const objectDetailsData = schema && data && data[schema.kind!]?.edges[0]?.node;

  if (!objectDetailsData) {
    return (
      <div className="flex column justify-center">
        <NoDataFound message="No item found for that id." />
      </div>
    );
  }

  if (objectKind === ARTIFACT_OBJECT) {
    return <ArtifactsDetails />;
  }

  if (objectKind === GRAPHQL_QUERY_OBJECT) {
    return (
      <Content>
        <GraphqlQueryDetailsPage />
      </Content>
    );
  }

  return (
    <Content>
      <Card className="p-2 pt-0">
        <ObjectItemDetails
          schema={schema}
          objectDetailsData={objectDetailsData}
          permission={permission}
          taskData={data[TASK_OBJECT]}
        />
      </Card>
    </Content>
  );
}

export const Component = ObjectDetailsPage;
