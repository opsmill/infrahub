import { CheckIcon, XIcon } from "lucide-react";
import React from "react";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Row } from "@/shared/components/container";
import { RelationshipManyInput } from "@/shared/components/inputs/relationship-many";
import { RelationshipInput } from "@/shared/components/inputs/relationship-one";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { useOnClickOutside } from "@/shared/hooks/useOnClickOutside";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import { InlineEditInput } from "@/entities/nodes/object/ui/object-details/object-data-display/inline-edit-input";
import type {
  NodeAttributeWithMetadata,
  NodeCore,
  NodeRelationshipManyWithMetadata,
  NodeRelationshipOneWithMetadata,
} from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export type InlineEditProps = InlineEditAllowedProps & {
  permission: Permission;
};

export function InlineEdit({ children, permission, ...props }: InlineEditProps) {
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

  if (props.fieldSchema.read_only) {
    return <InlineEditDisabled message="read-only">{children}</InlineEditDisabled>;
  }

  return <InlineEditAllowed {...props}>{children}</InlineEditAllowed>;
}

interface InlineEditDisabledProps {
  children: React.ReactNode;
  message?: string;
}

export function InlineEditDisabled({ children, message }: InlineEditDisabledProps) {
  return (
    <Row className="group p-2">
      {children}
      {message && (
        <span className="ml-auto hidden text-neutral-400 group-hover:block">{message}</span>
      )}
    </Row>
  );
}

type InlineEditAllowedProps = EditingModeProps & {
  children: React.ReactNode;
};

function InlineEditAllowed(props: InlineEditAllowedProps) {
  const [isEditing, setIsEditing] = React.useState(false);

  if (isEditing) {
    return (
      <EditingMode
        {...props}
        onSuccess={() => setIsEditing(false)}
        onCancel={() => setIsEditing(false)}
      />
    );
  }

  return (
    <Row
      className="cursor-pointer overflow-hidden rounded-lg px-2 py-3 hover:bg-neutral-100"
      onDoubleClick={() => setIsEditing(true)}
    >
      {props.children}
    </Row>
  );
}

type AttributeEditingModeProps = {
  type: "attribute";
  fieldSchema: AttributeSchema;
  fieldData: NodeAttributeWithMetadata;
};

type RelationshipEditingModeProps = {
  type: "relationship";
  fieldSchema: RelationshipSchema;
  fieldData: NodeRelationshipOneWithMetadata | NodeRelationshipManyWithMetadata;
};

type EditingModeProps = {
  objectKind: string;
  objectId: string;
} & (AttributeEditingModeProps | RelationshipEditingModeProps);

function EditingMode(props: EditingModeProps & { onSuccess: () => void; onCancel: () => void }) {
  const { objectKind, objectId, fieldSchema, onSuccess, onCancel } = props;
  const [value, setValue] = React.useState(() => getInitialValue(props));
  const ref = React.useRef<HTMLFormElement>(null);
  useOnClickOutside(ref, onCancel);

  const { mutate, isPending } = useUpdateObjectMutation({
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
      onSuccess();
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
        [fieldSchema.name]: serializeValue(props, value),
      },
    });
  };

  return (
    <form
      ref={ref}
      onSubmit={(e) => {
        e.preventDefault();
        handleSave();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") onCancel();
      }}
    >
      <Row>
        {renderInput(props, value, setValue)}
        <Button
          type="submit"
          variant="primary"
          size="square"
          className="size-8 shrink-0"
          disabled={isPending}
          isLoading={isPending}
        >
          {!isPending && <CheckIcon className="size-4" />}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="square"
          className="size-8 shrink-0"
          disabled={isPending}
          onClick={onCancel}
        >
          <XIcon className="size-4" />
        </Button>
      </Row>
    </form>
  );
}

function getInitialValue(props: EditingModeProps): unknown {
  if (props.type === "attribute") {
    return props.fieldData.value;
  }

  const isMany = props.fieldSchema.cardinality === "many";
  if (isMany) {
    const manyData = props.fieldData as NodeRelationshipManyWithMetadata;
    return manyData.edges.map((edge) => edge.node).filter((node): node is NodeCore => !!node);
  }

  const oneData = props.fieldData as NodeRelationshipOneWithMetadata;
  return oneData.node;
}

function serializeValue(props: EditingModeProps, value: unknown): unknown {
  if (props.type === "attribute") {
    return { value };
  }

  const isMany = props.fieldSchema.cardinality === "many";
  if (isMany) {
    const nodes = value as NodeCore[];
    return nodes.length > 0 ? nodes.map((node) => ({ id: node.id })) : null;
  }

  const node = value as NodeCore | null;
  return node ? { id: node.id } : null;
}

function renderInput(
  props: EditingModeProps,
  value: unknown,
  onChange: (value: unknown) => void
): React.ReactNode {
  if (props.type === "attribute") {
    return (
      <InlineEditInput attributeSchema={props.fieldSchema} value={value} onChange={onChange} />
    );
  }

  const isMany = props.fieldSchema.cardinality === "many";
  if (isMany) {
    return (
      <RelationshipManyInput
        peer={props.fieldSchema.peer}
        value={(value as NodeCore[]) ?? []}
        onChange={(newValue) => onChange(newValue)}
      />
    );
  }

  return (
    <RelationshipInput
      peer={props.fieldSchema.peer}
      value={value as NodeCore | null}
      onChange={(newValue) => onChange(newValue as NodeCore | null)}
    />
  );
}
