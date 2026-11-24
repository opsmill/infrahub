import { Button, type ButtonProps, Sheet, Tooltip } from "@infrahub/ui";
import { useState } from "react";

import { Icon } from "@/shared/components/display/icon";
import { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm from "@/shared/components/form/object-form";

import { ARTIFACT_OBJECT } from "@/entities/artifacts/domain/model/artifact";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface ObjectCreateFormTriggerProps extends ButtonProps {
  schema: ModelSchema;
  onSuccess?: (newObject: any) => void;
  permission: Permission;
}

export const ObjectCreateFormTrigger = ({
  schema,
  onSuccess,
  permission,
  ...props
}: ObjectCreateFormTriggerProps) => {
  const [showCreateDrawer, setShowCreateDrawer] = useState(false);
  const { isAllowed, message } = permission.create;

  if (schema.kind === ARTIFACT_OBJECT) {
    return null;
  }

  return (
    <>
      <Tooltip message={message}>
        <Button
          data-testid="create-object-button"
          size="sm"
          isDisabledAndFocusable={!isAllowed}
          onPress={() => setShowCreateDrawer(true)}
          {...props}
        >
          <Icon icon="mdi:plus" />
          Add {schema?.label}
        </Button>
      </Tooltip>

      <Sheet isOpen={showCreateDrawer} onOpenChange={setShowCreateDrawer}>
        <SlideOverTitle
          schema={schema}
          currentObjectLabel="New"
          title={`Create ${schema.label}`}
          subtitle={schema.description}
        />
        <ObjectForm
          onSuccess={async (result: any) => {
            setShowCreateDrawer(false);
            if (onSuccess) onSuccess(result);
          }}
          onCancel={() => setShowCreateDrawer(false)}
          kind={schema.kind!}
        />
      </Sheet>
    </>
  );
};
