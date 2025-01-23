import { CONFIG } from "@/config/config";
import { ARTIFACT_OBJECT, MENU_EXCLUDELIST } from "@/config/constants";
import { Generate } from "@/entities/artifacts/ui/generate";
import { getObjectDetailsPaginated } from "@/entities/nodes/api/getObjectDetails";
import {
  getSchemaObjectColumns,
  getTabs,
} from "@/entities/nodes/object-items/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { getPermission } from "@/entities/permission/utils";
import { genericsState, schemaState } from "@/entities/schema/stores/schema.atom";
import useQuery from "@/shared/api/graphql/useQuery";
import { constructPath } from "@/shared/api/rest/fetch";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { File } from "@/shared/components/file";
import LoadingScreen from "@/shared/components/loading-screen";
import { PropertyList } from "@/shared/components/table/property-list";
import { Badge } from "@/shared/components/ui/badge";
import { Link } from "@/shared/components/ui/link";
import { useTitle } from "@/shared/hooks/useTitle";
import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { Navigate } from "react-router-dom";
import { ARTIFACT_RELATIONSHIPS_BLACKLIST } from "../constants";

export default function ArtifactsDetails({ artifactId }: { artifactId: string }) {
  const objectid = artifactId;

  const [schemaList] = useAtom(schemaState);
  const [genericList] = useAtom(genericsState);
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
    return <LoadingScreen />;
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

  const properies = [
    {
      name: "Status",
      value: <Badge>{objectDetailsData?.status?.value}</Badge>,
    },
    ...(schema?.relationships ?? [])
      .filter(({ name }) => !ARTIFACT_RELATIONSHIPS_BLACKLIST.includes(name))
      .map((schemaRelationship) => {
        const relationshipData = objectDetailsData[schemaRelationship.name]?.node;

        return {
          name: schemaRelationship.label || schemaRelationship.name,
          value: relationshipData && (
            <Link
              to={constructPath(
                getObjectDetailsUrl(relationshipData.id, relationshipData.__typename)
              )}
            >
              {relationshipData?.display_label}
            </Link>
          ),
        };
      }),
  ];

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-4">
          <Generate
            label="Re-generate"
            artifactid={objectid}
            definitionid={objectDetailsData?.definition?.node?.id}
          />

          {objectDetailsData?.checksum?.value && (
            <CopyToClipboard
              text={objectDetailsData?.checksum?.value}
              size={"default"}
              variant={"outline"}
            >
              Checksum
            </CopyToClipboard>
          )}

          {objectDetailsData?.storage_id?.value && (
            <CopyToClipboard
              text={objectDetailsData?.storage_id?.value}
              size={"default"}
              variant={"outline"}
            >
              Storage ID
            </CopyToClipboard>
          )}
        </div>

        <PropertyList properties={properies} />
      </div>

      <File url={fileUrl} contentType={contentType} />
    </div>
  );
}
