import { Button, type ButtonProps, Sheet, Tooltip } from "@infrahub/ui";
import { useState } from "react";

import { Icon } from "@/shared/components/display/icon";
import { SlideOverTitle } from "@/shared/components/display/slide-over";

import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import ObjectEdit from "@/entities/nodes/object/ui/object-edit/object-item-edit-paginated";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface ObjectEditSlideOverTriggerProps extends ButtonProps {
  data: any;
  schema: ModelSchema;
  onUpdateComplete?: () => void;
  permission: Permission;
}

const ObjectEditSlideOverTrigger = ({
  data,
  schema,
  onUpdateComplete,
  permission,
  ...props
}: ObjectEditSlideOverTriggerProps) => {
  const [isEditDrawerOpen, setIsEditDrawerOpen] = useState(false);

  const editButton = !permission.create.isAllowed ? (
    <Tooltip message={permission.create.message ?? undefined}>
      <Button
        className="ml-auto"
        variant="outline"
        size="xs"
        shape="circle"
        isDisabledAndFocusable
        data-testid="edit-button"
        {...props}
      >
        <Icon icon="mdi:pencil" />
      </Button>
    </Tooltip>
  ) : (
    <Button
      className="ml-auto"
      variant="outline"
      size="xs"
      shape="circle"
      onPress={() => setIsEditDrawerOpen(true)}
      data-testid="edit-button"
      {...props}
    >
      <Icon icon="mdi:pencil" />
    </Button>
  );

  return (
    <>
      {editButton}

      <Sheet isOpen={isEditDrawerOpen} onOpenChange={setIsEditDrawerOpen}>
        <SlideOverTitle
          schema={schema}
          currentObjectLabel={getNodeLabel(data)}
          title={`Edit ${getNodeLabel(data)}`}
          subtitle={data?.description?.value}
        />
        <ObjectEdit
          closeDrawer={() => setIsEditDrawerOpen(false)}
          onUpdateComplete={() => {
            onUpdateComplete?.();
            setIsEditDrawerOpen(false);
          }}
          objectId={data.id}
          objectKind={schema.kind!}
        />
      </Sheet>
    </>
  );
};

export default ObjectEditSlideOverTrigger;
