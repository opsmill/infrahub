import { ButtonProps, ButtonWithTooltip } from "@/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import { usePermission } from "@/hooks/usePermission";
import ObjectItemEditComponent from "@/screens/object-item-edit/object-item-edit-paginated";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

interface ObjectEditSlideOverTriggerProps extends ButtonProps {
  data: any;
  schema: IModelSchema;
  onUpdateComplete?: () => void;
}
const ObjectEditSlideOverTrigger = ({
  data,
  schema,
  onUpdateComplete,
  ...props
}: ObjectEditSlideOverTriggerProps) => {
  const permission = usePermission();
  const [isEditDrawerOpen, setIsEditDrawerOpen] = useState(false);

  return (
    <>
      <ButtonWithTooltip
        className="ml-auto"
        variant="outline"
        size="icon"
        onClick={() => setIsEditDrawerOpen(true)}
        disabled={!permission.write.allow}
        tooltipEnabled={!permission.write.allow}
        tooltipContent={permission.write.message ?? undefined}
        data-testid="edit-button"
        {...props}>
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
        setOpen={setIsEditDrawerOpen}>
        <ObjectItemEditComponent
          closeDrawer={() => setIsEditDrawerOpen(false)}
          onUpdateComplete={onUpdateComplete}
          objectid={data.id}
          objectname={schema.kind!}
        />
      </SlideOver>
    </>
  );
};

export default ObjectEditSlideOverTrigger;
