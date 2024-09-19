import React, { forwardRef, useState } from "react";
import { Icon } from "@iconify-icon/react";
import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { useMutation } from "@/hooks/useQuery";
import ModalDelete from "@/components/modals/modal-delete";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import DynamicForm from "@/components/form/dynamic-form";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { ENUM_ADD_MUTATION, ENUM_REMOVE_MUTATION } from "@/graphql/mutations/schema/enum";
import { isRequired } from "@/components/form/utils/validation";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/components/ui/combobox";
import { AttributeSchema } from "@/screens/schema/types";

export interface EnumDeleteButtonProps extends ButtonProps {
  fieldSchema: AttributeSchema;
  schema: IModelSchema;
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
          className="ml-auto text-red-800 h-6"
          onClick={(e) => {
            e.stopPropagation();
            setShowDeleteModal(true);
          }}
          {...props}>
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
          setOpen={setShowDeleteModal}
          onCancel={() => setShowDeleteModal(false)}
          onDelete={handleDelete}
          open={showDeleteModal}
          isLoading={loading}
        />
      </>
    );
  }
);

interface EnumAddActionProps {
  schema?: IModelSchema;
  field?: AttributeSchema;
  addOption: (item: string | number) => void;
}

export const EnumAddAction: React.FC<EnumAddActionProps> = ({ schema, field, addOption }) => {
  const [open, setOpen] = useState(false);
  const [addEnum] = useMutation(ENUM_ADD_MUTATION);

  if (!schema || !field) return null;

  return (
    <div className="p-2 pt-0">
      <Button
        className="w-full bg-custom-blue-700/10 border border-custom-blue-700/20 text-custom-blue-700 enabled:hover:bg-custom-blue-700/20"
        onClick={() => setOpen(!open)}>
        + Add option
      </Button>

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
        offset={1}>
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
  schema?: IModelSchema;
  className?: string;
  onChange: (value: string | number | null) => void;
}

export const Enum = forwardRef<HTMLButtonElement, EnumProps>(
  ({ items, value, fieldSchema, schema, onChange, ...props }, ref) => {
    const [localItems, setLocalItems] = useState(items);
    const [open, setOpen] = useState(false);

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

        <ComboboxContent>
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
                {...props}>
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
