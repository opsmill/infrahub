import { ARTIFACT_OBJECT, GRAPHQL_QUERY_OBJECT, TASK_OBJECT } from "@/config/constants";
import ArtifactsDetails from "@/entities/artifacts/ui/artifact-details";
import { useObjectDetails } from "@/entities/nodes/hooks/useObjectDetails";
import ObjectItemDetails from "@/entities/nodes/object-item-details/object-item-details-paginated";
import { genericsState, profilesAtom, schemaState } from "@/entities/schema/stores/schema.atom";
import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { NetworkStatus } from "@apollo/client";
import { useAtomValue } from "jotai";
import { Navigate, useParams } from "react-router";
import GraphqlQueryDetailsPage from "./CoreGraphQLQuery/graphql-query-details";

export function ObjectDetailsPage() {
  const { objectKind, objectid } = useParams();

  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const schema = [...nodes, ...generics, ...profiles].find(({ kind }) => kind === objectKind);

  if (!schema) return <ErrorScreen message={`Object ${objectKind} not found.`} />;

  const { data, networkStatus, error, permission } = useObjectDetails(schema, objectid as string);

  if (networkStatus === NetworkStatus.loading) {
    return <LoadingIndicator className="h-[calc(100vh-10.5rem)]" />;
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
        <NoDataFound message={`No ${schema.label} found with ID: ${objectid}`} />
      </div>
    );
  }

  return (
    <ObjectItemDetails
      schema={schema}
      objectDetailsData={objectDetailsData}
      permission={permission}
      taskData={data[TASK_OBJECT]}
    />
  );
}

export const Component = () => {
  const { objectKind, objectid } = useParams();

  if (!objectid) {
    return <Navigate to={constructPath(`/objects/${objectKind}`)} />;
  }

  if (objectKind === ARTIFACT_OBJECT) {
    return <ArtifactsDetails artifactId={objectid} />;
  }

  if (objectKind === GRAPHQL_QUERY_OBJECT) {
    return <GraphqlQueryDetailsPage graphqlQueryId={objectid} />;
  }

  return <ObjectDetailsPage />;
};
