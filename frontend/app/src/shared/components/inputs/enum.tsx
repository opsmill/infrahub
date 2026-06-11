import { Icon } from "@iconify-icon/react";
import { Button, type ButtonProps, Sheet } from "@infrahub/ui";
import React from "react";

import { SlideOverTitle } from "@/shared/components/display/slide-over";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ModalDelete } from "@/shared/components/modals/modal-delete";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";

import type { AttributeSchema, ModelSchema } from "@/entities/schema/types";
import { useNamespace } from "@/entities/schema/ui/hooks/useNamespace";
import { useAddEnumMutation } from "@/entities/schema/ui/queries/add-enum.mutation";
import { useRemoveEnumMutation } from "@/entities/schema/ui/queries/remove-enum.mutation";

export interface EnumDeleteButtonProps extends Omit<ButtonProps, "value"> {
  fieldSchema: AttributeSchema;
  schema: ModelSchema;
  value: string | number;
  onDelete: (id: string | number) => void;
  ref?: React.Ref<HTMLButtonElement>;
}

export const EnumDeleteButton = ({
  fieldSchema,
  schema,
  onDelete,
  value,
}: EnumDeleteButtonProps) => {
  const [showDeleteModal, setShowDeleteModal] = React.useState(false);
  const namespace = useNamespace(schema?.namespace);
  const { mutateAsync: removeEnum, isPending: loading } = useRemoveEnumMutation();

  if (!namespace?.user_editable) return null;

  const handleDelete = async () => {
    if (!schema?.kind || !fieldSchema?.name) return;
    try {
      await removeEnum({ kind: schema.kind, attribute: fieldSchema.name, enum: String(value) });
      onDelete(value);
    } catch (error) {
      console.error("Error deleting enum:", error);
    }
  };

  return (
    <>
      <Button
        aria-label="Delete option"
        excludeFromTabOrder
        variant="ghost"
        size="sm"
        className="ml-auto h-6 text-red-800"
        onPress={() => {
          setShowDeleteModal(true);
        }}
      >
        <Icon icon="mdi:trash-can-outline" />
      </Button>

      <ModalDelete
        title="Delete"
        description={
          <>
            Are you sure you want to delete the enum{" "}
            <span className="font-semibold text-gray-800">{value}</span>?
          </>
        }
        isOpen={showDeleteModal}
        onOpenChange={setShowDeleteModal}
        onDelete={handleDelete}
        isLoading={loading}
      />
    </>
  );
};

interface EnumAddActionProps {
  schema?: ModelSchema;
  field?: AttributeSchema;
  addOption: (item: string | number) => void;
}

export const EnumAddAction = ({ schema, field, addOption }: EnumAddActionProps) => {
  const namespace = useNamespace(schema?.namespace);
  const [open, setOpen] = React.useState(false);
  const { mutateAsync: addEnum } = useAddEnumMutation();

  if (!schema || !field) return null;

  return (
    <div className="p-2 pt-0">
      {namespace?.user_editable && (
        <Button
          className="w-full border border-custom-blue-700/20 bg-custom-blue-700/10 text-custom-blue-700 not-data-disabled:data-hovered:bg-custom-blue-700/20"
          onPress={() => setOpen(!open)}
        >
          + Add option
        </Button>
      )}

      <Sheet isOpen={open} onOpenChange={setOpen}>
        <SlideOverTitle
          schema={schema}
          currentObjectLabel={field?.label}
          title="Add a new option"
          subtitle={field?.description}
        />
        <DynamicForm
          fields={[
            {
              name: "enum",
              label: "Enum name",
              type: field.kind === "Number" ? "Number" : "Text",
              rules: {
                required: true,
                validate: {
                  required: isRequired,
                },
              },
            },
          ]}
          onSubmit={async (formData) => {
            if (!schema.kind) return;
            const newEnumValue = formData.enum.value;
            await addEnum({
              kind: schema.kind,
              attribute: field.name,
              enum: String(newEnumValue),
            });
            addOption(newEnumValue as string | number);
            setOpen(false);
          }}
          onCancel={() => setOpen(false)}
          className="p-4"
        />
      </Sheet>
    </div>
  );
};

export interface EnumProps {
  items: Array<string | number>;
  value: string | number | null;
  fieldSchema?: AttributeSchema;
  schema?: ModelSchema;
  className?: string;
  onChange: (value: string | number | null) => void;
  defaultOpen?: boolean;
  fitTriggerWidth?: boolean;
  ref?: React.Ref<HTMLButtonElement>;
}

export const Enum = ({
  items,
  value,
  fieldSchema,
  schema,
  onChange,
  defaultOpen = false,
  fitTriggerWidth = false,
  ref,
  ...props
}: EnumProps) => {
  const [localItems, setLocalItems] = React.useState(items);
  const [open, setOpen] = React.useState(defaultOpen);

  const handleAddOption = (newOption: string | number) => {
    setLocalItems([...localItems, newOption]);
    onChange(newOption);
  };

  const handleDeleteOption = (deletedItem: string | number) => {
    setLocalItems(localItems.filter((item) => item !== deletedItem));
    if (value === deletedItem) {
      onChange(null);
    }
  };

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger ref={ref} {...props}>
        {value}
      </ComboboxTrigger>

      <ComboboxContent fitTriggerWidth={fitTriggerWidth}>
        <ComboboxList>
          <ComboboxEmpty>No enum found.</ComboboxEmpty>
          {localItems.map((item) => (
            <ComboboxItem
              key={item.toString()}
              value={item.toString()}
              selectedValue={value?.toString()}
              onSelect={() => {
                onChange(item === value ? null : item);
                setOpen(false);
              }}
              {...props}
            >
              {item}
              {schema && fieldSchema && (
                <EnumDeleteButton
                  schema={schema}
                  fieldSchema={fieldSchema}
                  value={item}
                  onDelete={handleDeleteOption}
                />
              )}
            </ComboboxItem>
          ))}
        </ComboboxList>

        <EnumAddAction schema={schema} field={fieldSchema} addOption={handleAddOption} />
      </ComboboxContent>
    </Combobox>
  );
};
