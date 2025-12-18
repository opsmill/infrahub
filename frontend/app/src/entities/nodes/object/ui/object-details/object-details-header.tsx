import { queryClient } from "@/shared/api/rest/client";
import { Row } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { Skeleton } from "@/shared/components/skeleton";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/object-details/node-metadata-popover";
import { ObjectDetailsButton } from "@/entities/nodes/object/ui/object-details-button";
import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeAttribute } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

interface ObjectDetailsHeaderProps {
  schema: ModelSchema;
  objectId: string;
}

export function ObjectDetailsHeader({ schema, objectId }: ObjectDetailsHeaderProps) {
  const {
    data: objectDetailsData,
    isPending,
    isRefetching,
    error,
  } = useGetObject({ objectSchema: schema, objectId });

  if (error) return null;

  const title = isPending ? (
    <Skeleton className="h-6 w-60" />
  ) : (
    <Row>
      {objectDetailsData ? getNodeLabel(objectDetailsData) : `${schema.label} not found`}
      <NodeMetadataPopover objectId={objectId} objectKind={schema.kind!} />
      <ObjectDetailsButton
        id={objectId}
        objectKind={schema.kind!}
        data-testid="object-details-button"
        hfid={objectDetailsData?.hfid && JSON.stringify(objectDetailsData?.hfid)}
      />
    </Row>
  );

  return (
    <Content.CardTitle
      title={title}
      description={
        (objectDetailsData?.description as NodeAttribute | undefined)?.value ?? schema.description
      }
      isReloadLoading={isRefetching}
      reload={async () => {
        await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
      }}
      end={
        <ObjectHelpButton
          kind={schema.kind}
          documentationUrl={schema.documentation}
          className="ml-auto"
        />
      }
      data-testid="object-header"
    />
  );
}
