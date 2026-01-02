import { Icon } from "@iconify-icon/react";
import { PencilLineIcon, RefreshCwIcon } from "lucide-react";
import { useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import {
  Button,
  ButtonWithTooltip,
  LinkButton,
} from "@/shared/components/buttons/button-primitive";
import { Row } from "@/shared/components/container";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { classNames } from "@/shared/utils/common";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/object-details/node-metadata-popover";
import { ObjectDetailsMenu } from "@/entities/nodes/object/ui/object-details/object-details-menu";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { DetailsButtons } from "@/entities/nodes/object-item-details/action-buttons/details-buttons";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
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
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  const {
    data: objectData,
    isPending,
    isRefetching,
    error,
  } = useGetObject({ objectSchema, objectId });

  if (isPending) {
    return (
      <HeaderContainer>
        <Skeleton className="h-8 w-60" />
        <Skeleton className="ml-auto h-8 w-25" />
      </HeaderContainer>
    );
  }

  if (error) return null;

  const nodeLabel = getNodeLabel(objectData);
  const isEditAllowed = permission.update.isAllowed;

  return (
    <>
      <HeaderContainer>
        <h2 className="truncate font-semibold text-xl">{nodeLabel}</h2>
        <NodeMetadataPopover objectId={objectId} objectKind={objectSchema.kind!} />

        <Button
          size="icon"
          variant="ghost"
          className="text-gray-500"
          isLoading={isRefetching}
          onClick={() => queryClient.invalidateQueries({ queryKey: objectQueryKeys.all })}
        >
          <RefreshCwIcon className={classNames("size-3.5", isRefetching && "animate-spin")} />
        </Button>

        <DetailsButtons schema={objectSchema} objectDetailsData={objectData} className="ml-auto" />

        <ButtonWithTooltip
          variant="outline"
          size="sm"
          disabled={!isEditAllowed}
          onClick={() => setIsEditModalOpen(true)}
          tooltipContent={!isEditAllowed ? permission.update.message : undefined}
          tooltipEnabled={!isEditAllowed}
        >
          <PencilLineIcon className="mr-1 size-3.5" />
          Edit
        </ButtonWithTooltip>

        <LinkButton
          variant="outline"
          size="sm"
          to={constructPath("/schema", [{ name: "kind", value: objectSchema.kind }])}
        >
          <Icon icon="mdi:code-json" className="mr-1" />
          Schema
        </LinkButton>

        <ObjectDetailsMenu
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
        />
      </HeaderContainer>

      <SlideOver
        title={
          <SlideOverTitle
            schema={objectSchema}
            currentObjectLabel={nodeLabel}
            title={`Edit ${nodeLabel}`}
            subtitle={objectSchema.description}
          />
        }
        open={isEditModalOpen}
        setOpen={setIsEditModalOpen}
      >
        <ObjectItemEditComponent
          closeDrawer={() => setIsEditModalOpen(false)}
          onUpdateComplete={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
            setIsEditModalOpen(false);
          }}
          objectId={objectData.id!}
          objectname={objectSchema.kind!}
        />
      </SlideOver>
    </>
  );
}

export function HeaderContainer({ children }: { children: React.ReactNode }) {
  return (
    <Row className="w-full p-3 pb-1.5" data-testid="object-header">
      {children}
    </Row>
  );
}
