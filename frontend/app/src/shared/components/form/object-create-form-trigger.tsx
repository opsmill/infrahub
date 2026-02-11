import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm from "@/shared/components/form/object-form";
import { ARTIFACT_OBJECT } from "@/shared/config/constants";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getActionAvailability } from "@/entities/branches/utils/get-action-tooltip";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

import { type ButtonProps, ButtonWithTooltip } from "../ui/button";

interface ObjectCreateFormTriggerProps
  extends Omit<ButtonProps, "disabled" | "tooltipEnabled" | "tooltipContent"> {
  schema: ModelSchema;
  onSuccess?: (newObject: any) => void;
  permission: Permission;
}

export const ObjectCreateFormTrigger = ({
  schema,
  onSuccess,
  isLoading,
  permission,
  ...props
}: ObjectCreateFormTriggerProps) => {
  const [showCreateDrawer, setShowCreateDrawer] = useState(false);
  const { currentBranch } = useCurrentBranch();

  if (schema.kind === ARTIFACT_OBJECT) {
    return null;
  }

  const { isAllowed, tooltipMessage } = getActionAvailability(
    currentBranch.status,
    permission.create
  );

  return (
    <>
      <ButtonWithTooltip
        data-cy="create"
        data-testid="create-object-button"
        disabled={!isAllowed || isLoading}
        onClick={() => setShowCreateDrawer(true)}
        tooltipContent={tooltipMessage}
        tooltipEnabled={!isAllowed}
        {...props}
      >
        <Icon icon="mdi:plus" className="mr-1.5 text-sm" />
        Add {schema?.label}
      </ButtonWithTooltip>

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel="New"
            title={`Create ${schema.label}`}
            subtitle={schema.description}
          />
        }
        open={showCreateDrawer}
        setOpen={setShowCreateDrawer}
      >
        <ObjectForm
          onSuccess={async (result: any) => {
            setShowCreateDrawer(false);
            if (onSuccess) onSuccess(result);
          }}
          onCancel={() => setShowCreateDrawer(false)}
          kind={schema.kind!}
        />
      </SlideOver>
    </>
  );
};
