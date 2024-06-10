import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { usePermission } from "@/hooks/usePermission";
import ObjectItemEditComponent from "@/screens/object-item-edit/object-item-edit-paginated";
import { currentBranchAtom } from "@/state/state/atoms/branches.atom";
import { IModelSchema } from "@/state/state/atoms/schema.atom";
import { ChevronRightIcon } from "@heroicons/react/20/solid";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { ButtonProps, ButtonWithTooltip } from "../buttons/button-primitive";
import SlideOver from "../display/slide-over";

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
  const currentBranch = useAtomValue(currentBranchAtom);
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
          <div className="space-y-2">
            <div className="flex items-start">
              <div className="flex-grow flex items-center flex-wrap overflow-hidden">
                <span className="font-semibold text-gray-900 truncate">{schema.label}</span>
                <ChevronRightIcon
                  className="w-4 h-4 flex-shrink-0 mx-2 text-gray-400"
                  aria-hidden="true"
                />
                <span className="flex-grow text-gray-500 overflow-hidden break-words line-clamp-3">
                  {data.display_label}
                </span>
              </div>
              <div className="flex items-center ml-3">
                <Icon icon="mdi:layers-triple" />
                <span className="ml-1">{currentBranch?.name ?? DEFAULT_BRANCH_NAME}</span>
              </div>
            </div>
            <div>{schema.description}</div>
            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schema.kind}
            </span>
            <div className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-custom-blue-500 ring-1 ring-inset ring-custom-blue-500/10">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-custom-blue-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              ID: {data.id}
            </div>
          </div>
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
