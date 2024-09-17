import React, { forwardRef, useState } from "react";
import { Icon } from "@iconify-icon/react";
import { Button } from "@/components/buttons/button-primitive";
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
} from "@/components/ui/combobox3";

export interface EnumItemProps extends React.ComponentPropsWithoutRef<typeof ComboboxItem> {
  fieldSchema: {
    name: string;
  };
  schema: IModelSchema;
  onDelete: (id: unknown) => void;
}

export const EnumItem = React.forwardRef<React.ElementRef<typeof ComboboxItem>, EnumItemProps>(
  ({ fieldSchema, schema, onDelete, className, value, children, ...props }, ref) => {
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [removeEnum, { loading }] = useMutation(ENUM_REMOVE_MUTATION, {
      variables: { kind: schema.kind, attribute: fieldSchema.name, enum: value },
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
        <ComboboxItem ref={ref} value={value} {...props}>
          {value}
          <Button
            tabIndex={-1}
            variant="ghost"
            size="sm"
            className="ml-auto text-red-800 h-6"
            onClick={(e) => {
              e.stopPropagation();
              setShowDeleteModal(true);
            }}>
            <Icon icon="mdi:trash-can-outline" />
          </Button>
        </ComboboxItem>

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
  schema: IModelSchema;
  field: {
    label?: string;
    description?: string;
    kind?: string;
    name: string;
  };
  addOption: (item: unknown) => void;
}

export const EnumAddAction: React.FC<EnumAddActionProps> = ({ schema, field, addOption }) => {
  const [open, setOpen] = useState(false);
  const [addEnum] = useMutation(ENUM_ADD_MUTATION);

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
              addOption(newEnumValue);
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
  items: Array<unknown>;
  value: string | null;
  fieldSchema: {
    name: string;
    label?: string;
    description?: string;
    kind?: string;
  };
  schema: IModelSchema;
  className?: string;
  onChange: (value: unknown) => void;
}

export const Enum = forwardRef<HTMLButtonElement, EnumProps>(
  ({ items, value, fieldSchema, schema, onChange, ...props }, ref) => {
    const [localItems, setLocalItems] = useState(items);
    const [open, setOpen] = useState(false);

    const handleAddOption = (newOption: unknown) => {
      setLocalItems([...localItems, newOption]);
      onChange(newOption);
    };

    const handleDeleteOption = (deletedItemId: unknown) => {
      setLocalItems(localItems.filter((item) => item !== deletedItemId));
      if (value === deletedItemId) {
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
              <EnumItem
                key={item?.toString()}
                value={item as string}
                selectedValue={value}
                schema={schema}
                fieldSchema={fieldSchema}
                onSelect={() => {
                  onChange(item === value ? null : item);
                  setOpen(false);
                }}
                onDelete={handleDeleteOption}
              />
            ))}
          </ComboboxList>

          <EnumAddAction schema={schema} field={fieldSchema} addOption={handleAddOption} />
        </ComboboxContent>
      </Combobox>
    );
  }
);
