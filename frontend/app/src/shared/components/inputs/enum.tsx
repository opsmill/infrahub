import { Icon } from "@iconify-icon/react";
import React, { forwardRef, useState } from "react";

import { useMutation } from "@/shared/api/graphql/useQuery";
import { ModalDelete } from "@/shared/components/aria/modal-delete";
import { Button, type ButtonProps } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { isRequired } from "@/shared/components/form/utils/validation";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";

import { ENUM_ADD_MUTATION, ENUM_REMOVE_MUTATION } from "@/entities/schema/api/enum";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/types";
import { useNamespace } from "@/entities/schema/ui/hooks/useNamespace";

export interface EnumDeleteButtonProps extends ButtonProps {
  fieldSchema: AttributeSchema;
  schema: ModelSchema;
  value: string | number;
  onDelete: (id: string | number) => void;
}

export const EnumDeleteButton = React.forwardRef<HTMLButtonElement, EnumDeleteButtonProps>(
  ({ fieldSchema, schema, onDelete, className, value, children, ...props }, ref) => {
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [removeEnum, { loading }] = useMutation(ENUM_REMOVE_MUTATION, {
      variables: { kind: schema?.kind, attribute: fieldSchema?.name, enum: value },
    });

    const handleDelete = async () => {
      try {
        await removeEnum();
        onDelete(value);
      } catch (error) {
        console.error("Error deleting enum:", error);
      }
    };

    return (
      <>
        <Button
          ref={ref}
          tabIndex={-1}
          variant="ghost"
          size="sm"
          className="ml-auto h-6 text-red-800"
          onClick={(e) => {
            e.stopPropagation();
            setShowDeleteModal(true);
          }}
          {...props}
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
  }
);

interface EnumAddActionProps {
  schema?: ModelSchema;
  field?: AttributeSchema;
  addOption: (item: string | number) => void;
}

export const EnumAddAction: React.FC<EnumAddActionProps> = ({ schema, field, addOption }) => {
  const namespace = useNamespace(schema?.namespace);
  const [open, setOpen] = useState(false);
  const [addEnum] = useMutation(ENUM_ADD_MUTATION);

  if (!schema || !field) return null;

  return (
    <div className="p-2 pt-0">
      {namespace?.user_editable && (
        <Button
          className="w-full border border-custom-blue-700/20 bg-custom-blue-700/10 text-custom-blue-700 enabled:hover:bg-custom-blue-700/20"
          onClick={() => setOpen(!open)}
        >
          + Add option
        </Button>
      )}

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={field?.label}
            title="Add a new option"
            subtitle={field?.description}
          />
        }
        open={open}
        setOpen={setOpen}
        offset={1}
      >
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
            const newEnumValue = formData.enum.value;
            const { data } = await addEnum({
              variables: {
                kind: schema.kind,
                attribute: field.name,
                enum: newEnumValue,
              },
            });
            if (data?.SchemaEnumAdd?.ok) {
              addOption(newEnumValue as string | number);
              setOpen(false);
            }
          }}
          onCancel={() => setOpen(false)}
          className="p-4"
        />
      </SlideOver>
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
}

export const Enum = forwardRef<HTMLButtonElement, EnumProps>(
  (
    {
      items,
      value,
      fieldSchema,
      schema,
      onChange,
      defaultOpen = false,
      fitTriggerWidth = false,
      ...props
    },
    ref
  ) => {
    const [localItems, setLocalItems] = useState(items);
    const [open, setOpen] = useState(defaultOpen);

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
  }
);
