import { CheckIcon, PenLineIcon, XIcon } from "lucide-react";
import React from "react";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Row } from "@/shared/components/container";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { useOnClickOutside } from "@/shared/hooks/useOnClickOutside";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import { InlineEditInput } from "@/entities/nodes/object/ui/object-details/object-data-display/inline-edit-input";
import type { NodeAttributeWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { AttributeSchema } from "@/entities/schema/types";

export interface InlineEditProps extends InlineEditAllowedProps {
  permission: Permission;
  objectKind: string;
  objectId: string;
}

export function InlineEdit({
  children,
  fieldSchema,
  fieldData,
  permission,
  objectKind,
  objectId,
}: InlineEditProps) {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <InlineEditDisabled>{children}</InlineEditDisabled>;
  }

  if (!permission.update.isAllowed) {
    return (
      <InlineEditDisabled message="You don’t have permission to edit">
        {children}
      </InlineEditDisabled>
    );
  }

  if (fieldSchema.read_only) {
    return <InlineEditDisabled message="read-only">{children}</InlineEditDisabled>;
  }

  return (
    <InlineEditAllowed
      fieldSchema={fieldSchema}
      fieldData={fieldData}
      objectKind={objectKind}
      objectId={objectId}
    >
      {children}
    </InlineEditAllowed>
  );
}

interface InlineEditDisabledProps {
  children: React.ReactNode;
  message?: string;
}

function InlineEditDisabled({ children, message }: InlineEditDisabledProps) {
  return (
    <Row className="group grow p-2">
      {children}
      {message && (
        <span className="ml-auto hidden text-neutral-400 group-hover:block">{message}</span>
      )}
    </Row>
  );
}

interface InlineEditAllowedProps {
  fieldSchema: AttributeSchema;
  fieldData: NodeAttributeWithMetadata;
  children: React.ReactNode;
  objectKind: string;
  objectId: string;
}

function InlineEditAllowed({
  children,
  fieldSchema,
  fieldData,
  objectKind,
  objectId,
}: InlineEditAllowedProps) {
  const [isEditing, setIsEditing] = React.useState(false);

  if (isEditing) {
    return (
      <EditingMode
        fieldSchema={fieldSchema}
        defaultValue={fieldData.value}
        objectKind={objectKind}
        objectId={objectId}
        onSuccess={() => setIsEditing(false)}
        onCancel={() => setIsEditing(false)}
      />
    );
  }

  return (
    <Row
      className="group grow cursor-pointer rounded-lg py-3 px-2 hover:bg-neutral-100"
      onClick={() => setIsEditing(true)}
    >
      {children}
      <PenLineIcon className="ml-auto hidden size-3.5 text-neutral-400 group-hover:block" />
    </Row>
  );
}

interface EditingModeProps {
  fieldSchema: AttributeSchema;
  defaultValue: unknown;
  objectKind: string;
  objectId: string;
  onSuccess?: () => Promise<void> | void;
  onCancel: () => void;
}

function EditingMode({
  fieldSchema,
  defaultValue,
  objectKind,
  objectId,
  onSuccess,
  onCancel,
}: EditingModeProps) {
  const [value, setValue] = React.useState(defaultValue);
  const ref = React.useRef<HTMLDivElement>(null);
  useOnClickOutside(ref, onCancel);

  const { mutate, isPending } = useUpdateObjectMutation({
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
      onSuccess?.();
    },
    onError: (error) => {
      toast(<Alert type={ALERT_TYPES.ERROR} message={error.message} />);
    },
  });

  const handleSave = () => {
    mutate({
      objectKind,
      data: {
        id: objectId,
        [fieldSchema.name]: { value },
      },
    });
  };

  return (
    <Row className="grow" ref={ref}>
      <InlineEditInput attributeSchema={fieldSchema} value={value} onChange={setValue} />
      <Button
        variant="primary"
        size="square"
        className="shrink-0"
        disabled={isPending}
        isLoading={isPending}
        onClick={handleSave}
      >
        {!isPending && <CheckIcon className="size-4" />}
      </Button>
      <Button
        variant="outline"
        size="square"
        className="shrink-0"
        disabled={isPending}
        onClick={onCancel}
      >
        <XIcon className="size-4" />
      </Button>
    </Row>
  );
}
