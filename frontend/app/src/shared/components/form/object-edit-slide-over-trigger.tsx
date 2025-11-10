import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { type ButtonProps, ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";

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

  return (
    <>
      <ButtonWithTooltip
        className="ml-auto"
        variant="outline"
        size="icon"
        onClick={() => setIsEditDrawerOpen(true)}
        disabled={!permission.create.isAllowed}
        tooltipEnabled={!permission.create.isAllowed}
        tooltipContent={permission.create.message ?? undefined}
        data-testid="edit-button"
        {...props}
      >
        <Icon icon="mdi:pencil" />
      </ButtonWithTooltip>

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={data.display_label}
            title={`Edit ${data.display_label}`}
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
          objectid={data.id}
          objectname={schema.kind!}
        />
      </SlideOver>
    </>
  );
};

export default ObjectEditSlideOverTrigger;
