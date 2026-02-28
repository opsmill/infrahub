import { Row } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/loading/skeleton";

import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/object-details/node-metadata-popover";
import { ObjectDetailsMenu } from "@/entities/nodes/object/ui/object-details/object-details-menu";
import { RefreshButton } from "@/entities/nodes/object/ui/object-details/refresh-button";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { DetailsButtons } from "@/entities/nodes/object-item-details/action-buttons/details-buttons";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

interface ObjectDetailsHeaderProps {
  objectSchema: ModelSchema;
  objectId: string;
  permission: Permission;
}

export function ObjectDetailsHeader({
  objectSchema,
  objectId,
  permission,
}: ObjectDetailsHeaderProps) {
  const { data: objectData, isPending, error } = useGetObject({ objectSchema, objectId });

  if (isPending) {
    return (
      <HeaderContainer>
        <Skeleton className="h-8 w-60" />
        <Skeleton className="ml-auto h-8 w-25" />
      </HeaderContainer>
    );
  }

  if (error) return null;

  return (
    <HeaderContainer>
      <h2 className="truncate font-semibold text-xl">{getNodeLabel(objectData)}</h2>
      <NodeMetadataPopover objectId={objectId} objectKind={objectSchema.kind!} />

      <RefreshButton className="ml-auto" />

      <DetailsButtons
        schema={objectSchema}
        objectDetailsData={objectData}
        permission={permission}
      />

      <ObjectDetailsMenu
        objectSchema={objectSchema}
        objectData={objectData}
        permission={permission}
      />
    </HeaderContainer>
  );
}

export function HeaderContainer({ children }: { children: React.ReactNode }) {
  return (
    <Row className="w-full p-3 pb-1.5" data-testid="object-header">
      {children}
    </Row>
  );
}
