import { CONFIG } from "@/config/config";
import { getObjectDetailsPaginated } from "@/entities/nodes/api/getObjectDetails";
import {
  getSchemaObjectColumns,
  getTabs,
} from "@/entities/nodes/object-items/getSchemaObjectColumns";
import { ObjectInlineDisplay } from "@/entities/nodes/object/ui/object-inline-display";
import { ModelSchema } from "@/entities/schema/types";
import useQuery from "@/shared/api/graphql/useQuery";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { File } from "@/shared/components/file";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { gql } from "@apollo/client";
import ArtifactHeader from "./artifact-header";

export interface ArtifactsDetailsProps {
  artifactSchema: ModelSchema;
  artifactId: string;
}

export function ArtifactsDetails({ artifactId, artifactSchema }: ArtifactsDetailsProps) {
  const schemaKind: string = artifactSchema.kind as string;

  const columns = getSchemaObjectColumns({ schema: artifactSchema });
  const relationshipsTabs = getTabs(artifactSchema);

  const { loading, error, data } = useQuery(
    gql(
      getObjectDetailsPaginated({
        kind: artifactSchema.kind,
        columns,
        relationshipsTabs,
        objectid: artifactId,
        hasPermissions: true,
      })
    )
  );

  if (loading) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching object details." />;
  }

  if (!data?.[schemaKind]?.edges?.length) {
    return <NoDataFound message="No item found for that id." />;
  }

  const objectDetailsData = data[schemaKind].edges[0]?.node;
  if (!objectDetailsData) {
    return null;
  }

  const fileUrl = CONFIG.ARTIFACTS_CONTENT_URL(objectDetailsData?.storage_id?.value);
  const contentType = objectDetailsData.content_type?.value;

  return (
    <Content.Card className="flex flex-col gap-4 p-4">
      <ArtifactHeader
        name={objectDetailsData?.display_label}
        status={objectDetailsData?.status?.value}
        id={artifactId}
        hfid={objectDetailsData?.hfid && JSON.stringify(objectDetailsData?.hfid)}
        checksum={objectDetailsData?.checksum?.value}
        storageId={objectDetailsData?.storage_id?.value}
        definitionId={objectDetailsData?.definition?.node?.id}
      />

      <div className="flex flex-wrap gap-6">
        <ObjectInlineDisplay node={objectDetailsData.definition?.node} />
        <ObjectInlineDisplay node={objectDetailsData.object?.node} />
      </div>

      <File url={fileUrl} contentType={contentType} />
    </Content.Card>
  );
}
