import { CONFIG } from "@/config/config";
import { ARTIFACT_OBJECT, MENU_EXCLUDELIST } from "@/config/constants";
import { getObjectDetailsPaginated } from "@/entities/nodes/api/getObjectDetails";
import {
  getSchemaObjectColumns,
  getTabs,
} from "@/entities/nodes/object-items/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { getPermission } from "@/entities/permission/utils";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import useQuery from "@/shared/api/graphql/useQuery";
import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { File } from "@/shared/components/file";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { PropertyList } from "@/shared/components/table/property-list";
import { Link } from "@/shared/components/ui/link";
import { useTitle } from "@/shared/hooks/useTitle";
import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { Navigate, useParams } from "react-router";
import ArtifactHeader from "./artifact-header";

function ArtifactsDetails() {
  const { objectid } = useParams();

  const [schemaList] = useAtom(nodeSchemasAtom);
  const [schemaLabels] = useAtom(schemaKindLabelState);
  const [genericList] = useAtom(genericSchemasAtom);
  const schema = schemaList.find((s) => s.kind === ARTIFACT_OBJECT);
  const generic = genericList.find((s) => s.kind === ARTIFACT_OBJECT);
  useTitle("Artifact details");

  const schemaData = generic || schema;

  if ((schemaList?.length || genericList?.length) && !schemaData) {
    // If there is no schema nor generics, go to home page
    return <Navigate to="/" />;
  }

  if (schemaData && MENU_EXCLUDELIST.includes(schemaData.kind)) {
    return <Navigate to="/" />;
  }

  const columns = getSchemaObjectColumns({ schema: schemaData });
  const relationshipsTabs = getTabs(schemaData);

  const queryString = schemaData
    ? getObjectDetailsPaginated({
        kind: schemaData.kind,
        columns,
        relationshipsTabs,
        objectid,
        hasPermissions: true,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  // TODO: Find a way to avoid querying object details if we are on a tab
  const { loading, error, data } = useQuery(query, { skip: !schemaData });

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching object details." />;
  }

  if (loading || !schemaData) {
    return <LoadingIndicator className="h-full" />;
  }

  if (!data || (data && !data[schemaData.kind]?.edges?.length)) {
    return <NoDataFound message="No item found for that id." />;
  }

  const objectDetailsData = data[schemaData.kind]?.edges[0]?.node;

  const permission = getPermission(
    schemaData.kind && data && data[schemaData?.kind]?.permissions?.edges
  );

  if (!objectDetailsData) {
    return null;
  }

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  const fileUrl = CONFIG.ARTIFACTS_CONTENT_URL(objectDetailsData?.storage_id?.value);
  const contentType = objectDetailsData?.content_type?.value;

  const properties = [
    {
      name: schemaLabels[objectDetailsData?.object?.node?.__typename],
      value: (
        <Link
          to={constructPath(
            getObjectDetailsUrl(
              objectDetailsData?.object?.node?.id,
              objectDetailsData?.object?.node?.__typename
            )
          )}
        >
          {objectDetailsData?.object?.node?.display_label}
        </Link>
      ),
    },
    {
      name: schemaLabels[objectDetailsData?.definition?.node?.__typename],
      value: (
        <Link
          to={constructPath(
            getObjectDetailsUrl(
              objectDetailsData?.definition?.node?.id,
              objectDetailsData?.definition?.node?.__typename
            )
          )}
        >
          {objectDetailsData?.definition?.node?.display_label}
        </Link>
      ),
    },
  ];

  return (
    <Content.Card className="p-4">
      <ArtifactHeader
        name={objectDetailsData?.display_label}
        status={objectDetailsData?.status?.value}
        id={objectid}
        hfid={objectDetailsData?.hfid && JSON.stringify(objectDetailsData?.hfid)}
        checksum={objectDetailsData?.checksum?.value}
        storageId={objectDetailsData?.storage_id?.value}
        definitionId={objectDetailsData?.definition?.node?.id}
      />

      <div className="flex flex-col gap-4">
        <PropertyList properties={properties} />

        <File url={fileUrl} contentType={contentType} />
      </div>
    </Content.Card>
  );
}

export const Component = () => {
  return <ArtifactsDetails />;
};

export default Component;
