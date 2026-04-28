import { Icon } from "@iconify-icon/react";
import { Button, type ButtonProps } from "@infrahub/ui";
import { useState } from "react";

import { Tooltip } from "@/shared/components/aria/tooltip";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

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

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={getNodeLabel(data)}
            title={`Edit ${getNodeLabel(data)}`}
            subtitle={data?.description?.value}
          />
        }
        open={isEditDrawerOpen}
        setOpen={setIsEditDrawerOpen}
      >
        <ObjectItemEditComponent
          closeDrawer={() => setIsEditDrawerOpen(false)}
          onUpdateComplete={() => {
            onUpdateComplete?.();
            setIsEditDrawerOpen(false);
          }}
          objectId={data.id}
          objectname={schema.kind!}
        />
      </SlideOver>
    </>
  );
};

export default ObjectEditSlideOverTrigger;
