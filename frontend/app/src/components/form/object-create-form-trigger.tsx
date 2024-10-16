import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import { ARTIFACT_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { Permission } from "@/screens/role-management/types";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Button, ButtonProps } from "../buttons/button-primitive";
import { Tooltip } from "../ui/tooltip";

interface ObjectCreateFormTriggerProps extends ButtonProps {
  schema: IModelSchema;
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

  if (schema.kind === ARTIFACT_OBJECT) {
    return null;
  }

  const isAllowed = permission.create.isAllowed;
  const tooltipMessage = permission.create.message;

  return (
    <>
      <Tooltip enabled={!isAllowed} content={tooltipMessage}>
        <Button
          data-cy="create"
          data-testid="create-object-button"
          disabled={!isAllowed || isLoading}
          onClick={() => setShowCreateDrawer(true)}
          {...props}
        >
          <Icon icon="mdi:plus" className="text-sm mr-1.5" />
          Add {schema?.label}
        </Button>
      </Tooltip>

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
            await graphqlClient.refetchQueries({ include: [schema.kind!] });
            if (onSuccess) onSuccess(result);
          }}
          onCancel={() => setShowCreateDrawer(false)}
          kind={schema.kind!}
        />
      </SlideOver>
    </>
  );
};
