import { Separator } from "@/shared/components/aria/separator";
import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Card } from "@/shared/components/ui/card";
import { CONFIG } from "@/shared/config/config";

import { assertArtifactObject } from "@/entities/artifacts/types";
import { ArtifactFile } from "@/entities/artifacts/ui/artifact-file";
import { NodeEvents } from "@/entities/events/ui/node-details-events";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { NodeDescription } from "@/entities/nodes/object/ui/node-description";
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

  const artifact = assertArtifactObject(data);
  if (!artifact) {
    return <ErrorScreen message="Artifact data is incomplete" />;
  }

  return (
    <div className="flex w-full grow flex-wrap gap-0.5 overflow-auto lg:flex-nowrap">
      <Content.Card className="flex grow flex-col">
        <Col className="gap-3 p-4 pb-2">
          <ArtifactHeader artifact={artifact} />

          <Separator />

          <Row className="gap-4">
            <NodeDescription node={artifact.definition.node} className="p-2" />
            <Separator orientation="vertical" />
            <NodeDescription node={artifact.object.node} className="p-2" />
          </Row>
        </Col>

        <div className="flex grow overflow-hidden p-1">
          <ArtifactFile
            artifactId={artifactId}
            url={CONFIG.ARTIFACTS_CONTENT_URL(artifact.storage_id.value)}
            contentType={artifact.content_type.value}
          />
        </div>
      </Content.Card>
      <Card className="min-w-[350px] p-0">
        <div className="border-gray-200 border-b p-2 font-semibold">Activities</div>
        <NodeEvents objectId={artifactId} objectKind={artifactKind} />
      </Card>
    </div>
  );
}
