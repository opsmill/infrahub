import { CONFIG } from "@/config/config";
import { ArtifactFile } from "@/entities/artifacts/ui/artifact-file";
import { NodeEvents } from "@/entities/events/ui/node-details-events";
import { useObjectDetails } from "@/entities/nodes/hooks/useObjectDetails";
import { NodeDescription } from "@/entities/nodes/object/ui/node-description";
import { ModelSchema } from "@/entities/schema/types";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Card } from "@/shared/components/ui/card";
import { Divider } from "@/shared/components/ui/divider";
import ArtifactHeader from "./artifact-header";

export interface ArtifactsDetailsProps {
  artifactSchema: ModelSchema;
  artifactId: string;
}

export function ArtifactsDetails({ artifactId, artifactSchema }: ArtifactsDetailsProps) {
  const artifactKind = artifactSchema.kind as string;
  const { loading, error, data } = useObjectDetails(artifactSchema, artifactId);

  if (loading) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={`Something went wrong when fetching artifact ${artifactId}`} />;
  }

  const objectDetailsData = data?.[artifactKind]?.edges?.[0]?.node;
  if (!objectDetailsData) {
    return <NoDataFound message={`No artifact found with id ${artifactId}`} />;
  }

  const fileUrl: string = CONFIG.ARTIFACTS_CONTENT_URL(objectDetailsData?.storage_id?.value);
  const contentType = objectDetailsData.content_type?.value;

  return (
    <div className="flex flex-wrap grow lg:flex-nowrap w-full gap-0.5 overflow-auto">
      <Content.Card className="flex flex-col grow">
        <div className="p-4 pb-2">
          <ArtifactHeader
            name={objectDetailsData?.display_label}
            status={objectDetailsData?.status?.value}
            id={artifactId}
            hfid={objectDetailsData?.hfid && JSON.stringify(objectDetailsData?.hfid)}
            checksum={objectDetailsData?.checksum?.value}
            storageId={objectDetailsData?.storage_id?.value}
            definitionId={objectDetailsData?.definition?.node?.id}
          />

          <Divider />

          <div className="flex gap-4">
            <NodeDescription node={objectDetailsData.definition?.node} className="p-2" />
            <div className="self-stretch w-px bg-gray-300" />
            <NodeDescription node={objectDetailsData.object?.node} className="p-2" />
          </div>
        </div>

        <div className="flex p-1 grow overflow-hidden">
          <ArtifactFile artifactId={artifactId} url={fileUrl} contentType={contentType} />
        </div>
      </Content.Card>
      <Card className="min-w-[350px] p-0">
        <div className="font-semibold p-2 border-b  border-gray-200">Activities</div>
        <NodeEvents objectId={artifactId} objectKind={artifactKind} />
      </Card>
    </div>
  );
}
