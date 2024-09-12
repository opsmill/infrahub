import { Icon } from "@iconify-icon/react";
import { Button, ButtonProps } from "../buttons/button-primitive";
import { Tooltip } from "../ui/tooltip";
import { usePermission } from "@/hooks/usePermission";
import { useState } from "react";
import { ACCOUNT_OBJECT, ARTIFACT_OBJECT } from "@/config/constants";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { isGeneric } from "@/utils/common";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import graphqlClient from "@/graphql/graphqlClientApollo";

interface ObjectCreateFormTriggerProps extends ButtonProps {
  schema: IModelSchema;
  onSuccess?: (newObject: any) => void;
}

export const ObjectCreateFormTrigger = ({
  schema,
  onSuccess,
  isLoading,
  ...props
}: ObjectCreateFormTriggerProps) => {
  const permission = usePermission();

  const [showCreateDrawer, setShowCreateDrawer] = useState(false);

  if (schema.kind === ARTIFACT_OBJECT) {
    return null;
  }

  const isAccount: boolean =
    schema.kind === ACCOUNT_OBJECT ||
    (!isGeneric(schema) && !!schema.inherit_from?.includes(ACCOUNT_OBJECT));

  const isAllowed = isAccount ? permission.isAdmin.allow : permission.write.allow;
  const tooltipMessage = isAccount ? permission.isAdmin.message : permission.isAdmin.message;

  return (
    <>
      <Tooltip enabled={!isAllowed} content={tooltipMessage}>
        <Button
          data-cy="create"
          data-testid="create-object-button"
          disabled={!isAllowed || isLoading}
          onClick={() => setShowCreateDrawer(true)}
          {...props}>
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
        setOpen={setShowCreateDrawer}>
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
