import { CONFIG } from "@/config/config";

import type { CoreArtifact } from "@/shared/api/graphql/generated/graphql";
import { Separator } from "@/shared/components/aria/separator";
import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Card } from "@/shared/components/ui/card";

import { ArtifactFile } from "@/entities/artifacts/ui/artifact-file";
import { NodeEvents } from "@/entities/events/ui/node-details-events";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { NodeDescription } from "@/entities/nodes/object/ui/node-description";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { ModelSchema } from "@/entities/schema/types";

import ArtifactHeader from "./artifact-header";

export interface ArtifactsDetailsProps {
  artifactSchema: ModelSchema;
  artifactId: string;
}

export function ArtifactsDetails({ artifactId, artifactSchema }: ArtifactsDetailsProps) {
  const artifactKind = artifactSchema.kind as string;
  const { isPending, error, data } = useGetObject({
    objectSchema: artifactSchema,
    objectId: artifactId,
  });

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const objectDetailsData = data as unknown as CoreArtifact;

  const fileUrl: string = CONFIG.ARTIFACTS_CONTENT_URL(objectDetailsData?.storage_id?.value);
  const contentType = objectDetailsData.content_type?.value;

  return (
    <div className="flex w-full grow flex-wrap gap-0.5 overflow-auto lg:flex-nowrap">
      <Content.Card className="flex grow flex-col">
        <Col className="gap-3 p-4 pb-2">
          <ArtifactHeader
            name={objectDetailsData ? getNodeLabel(objectDetailsData) : ""}
            status={objectDetailsData?.status?.value}
            id={artifactId}
            hfid={objectDetailsData?.hfid && JSON.stringify(objectDetailsData?.hfid)}
            checksum={objectDetailsData?.checksum?.value}
            storageId={objectDetailsData?.storage_id?.value}
            artifactDefinitionId={objectDetailsData?.definition?.node?.id}
          />

          <Separator />

          <Row className="gap-4">
            <NodeDescription node={objectDetailsData.definition?.node} className="p-2" />
            <Separator orientation="vertical" />
            <NodeDescription node={objectDetailsData.object?.node} className="p-2" />
          </Row>
        </Col>

        <div className="flex grow overflow-hidden p-1">
          <ArtifactFile artifactId={artifactId} url={fileUrl} contentType={contentType} />
        </div>
      </Content.Card>
      <Card className="min-w-[350px] p-0">
        <div className="border-gray-200 border-b p-2 font-semibold">Activities</div>
        <NodeEvents objectId={artifactId} objectKind={artifactKind} />
      </Card>
    </div>
  );
}
