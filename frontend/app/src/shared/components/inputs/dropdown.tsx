import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import React from "react";

import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ModalDelete } from "@/shared/components/modals/modal-delete";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import type { CommandItem } from "@/shared/components/ui/command";
import { classNames, getTextColor } from "@/shared/utils/common";

import type { AttributeSchema, ModelSchema } from "@/entities/schema/types";
import { useNamespace } from "@/entities/schema/ui/hooks/useNamespace";
import { useAddDropdownMutation } from "@/entities/schema/ui/queries/add-dropdown.mutation";
import { useRemoveDropdownMutation } from "@/entities/schema/ui/queries/remove-dropdown.mutation";

export interface DropdownOption {
  value: string;
  label: string;
  badge?: string;
  color?: string;
  description?: string;
}

export interface DropdownProps extends Omit<React.HTMLAttributes<HTMLButtonElement>, "onChange"> {
  value?: DropdownOption["value"] | null;
  items: Array<DropdownOption>;
  className?: string;
  onChange: (value: DropdownOption["value"] | null) => void;
  schema?: ModelSchema;
  field?: AttributeSchema;
  defaultOpen?: boolean;
  ref?: React.Ref<HTMLButtonElement>;
}

export interface DropdownItemProps extends React.ComponentPropsWithoutRef<typeof ComboboxItem> {
  fieldSchema?: {
    name: string;
  };
  schema?: ModelSchema;
  onDelete: (item: DropdownOption) => void;
  item: DropdownOption;
  ref?: React.Ref<React.ComponentRef<typeof CommandItem>>;
}

export const DropdownItem = ({
  fieldSchema,
  schema,
  onDelete,
  className,
  item,
  ref,
  ...props
}: DropdownItemProps) => {
  const [showDeleteModal, setShowDeleteModal] = React.useState(false);
  const { mutateAsync: removeDropdownOption, isPending: loading } = useRemoveDropdownMutation();

  return (
    <ComboboxItem ref={ref} className={classNames("rounded-none", className)} {...props}>
      <div className="w-full overflow-hidden">
        <div className="flex items-center justify-between">
          <Badge className="font-medium" style={getDropdownStyle(item.color)}>
            {item.label}
          </Badge>

          {item.badge && (
            <Badge className="font-medium" style={getDropdownStyle(item.color)}>
              {item.badge}
            </Badge>
          )}
        </div>
        <p className="truncate text-xs">{item.description}</p>
      </div>

      {schema && fieldSchema && (
        <>
          <Button
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
                Are you sure you want to delete the option{" "}
                <Badge
                  className="font-medium"
                  style={
                    item?.color
                      ? {
                          backgroundColor: item.color,
                          color: getTextColor(item.color),
                        }
                      : undefined
                  }
                >
                  {item.label}
                </Badge>{" "}
                ?
              </>
            }
            isOpen={showDeleteModal}
            onOpenChange={setShowDeleteModal}
            onDelete={async () => {
              if (!schema.kind) return;
              try {
                await removeDropdownOption({
                  kind: schema.kind,
                  attribute: fieldSchema.name,
                  dropdown: item.value,
                });
                onDelete(item);
              } catch (error) {
                console.error("Error deleting dropdown item:", error);
              }
            }}
            isLoading={loading}
          />
        </>
      )}
    </ComboboxItem>
  );
};

interface DropdownAddActionProps {
  schema: ModelSchema;
  field: AttributeSchema;
  addOption: (item: DropdownOption) => void;
}

export const DropdownAddAction = ({ schema, field, addOption }: DropdownAddActionProps) => {
  const namespace = useNamespace(schema.namespace);
  const [open, setOpen] = React.useState(false);
  const { mutateAsync: addDropdownItem } = useAddDropdownMutation();

  return (
    <div className="p-2 pt-0">
      {namespace?.user_editable && (
        <Button
          className="w-full border border-custom-blue-700/20 bg-custom-blue-700/10 text-custom-blue-700 not-data-disabled:data-hovered:bg-custom-blue-700/20"
          onPress={() => setOpen(!open)}
          data-testid="add-option-button"
        >
          + Add option
        </Button>
      )}

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={field?.label ?? ""}
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
              name: "value",
              label: "Value",
              type: "Text",
              rules: { required: true, validate: { required: isRequired } },
            },
            {
              name: "label",
              label: "Label",
              type: "Text",
            },
            {
              name: "color",
              label: "Color",
              type: "Color",
            },
            {
              name: "description",
              label: "Description",
              type: "Text",
            },
          ]}
          onSubmit={async (formData) => {
            if (!schema.kind) return;
            const result = await addDropdownItem({
              kind: schema.kind,
              attribute: field.name,
              dropdown: formData.value.value as string,
              label: formData.label?.value as string | undefined,
              color: formData.color?.value as string | undefined,
              description: formData.description?.value as string | undefined,
            });
            addOption({
              value: result.value,
              label: result.label ?? result.value,
              color: result.color ?? undefined,
              description: result.description ?? undefined,
            });
            setOpen(false);
          }}
          onCancel={() => setOpen(false)}
          className="p-4"
        />
      </SlideOver>
    </div>
  );
};

export const Dropdown = ({
  items,
  onChange,
  value,
  schema,
  field,
  defaultOpen,
  ref,
  ...props
}: DropdownProps) => {
  const [localItems, setLocalItems] = React.useState(items);
  const [open, setOpen] = React.useState(!!defaultOpen);

  const handleAddOption = (newOption: DropdownOption) => {
    setLocalItems([...localItems, newOption]);
    onChange(newOption.value);
  };

  const handleDeleteOption = (deletedItem: DropdownOption) => {
    setLocalItems(localItems.filter((item) => item.value !== deletedItem.value));
    if (value === deletedItem.value) {
      onChange(null);
    }
  };

  const selectItem = localItems.find((item) => item.value === value);

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <ComboboxTrigger ref={ref} style={getDropdownStyle(selectItem?.color)} {...props}>
        <div className="flex w-full items-center justify-between">
          {selectItem?.label}

          {selectItem?.badge && <Badge>{selectItem?.badge}</Badge>}
        </div>
      </ComboboxTrigger>

      <ComboboxContent fitTriggerWidth={false}>
        <ComboboxList>
          <ComboboxEmpty>No dropdown found.</ComboboxEmpty>
          {localItems.map((item) => (
            <DropdownItem
              key={item.value}
              schema={schema}
              fieldSchema={field}
              value={item.value}
              selectedValue={selectItem?.value}
              onSelect={() => {
                onChange(item.value === value ? null : item.value);
                setOpen(false);
              }}
              item={item}
              onDelete={handleDeleteOption}
            />
          ))}
        </ComboboxList>

        {schema && field && (
          <DropdownAddAction schema={schema} field={field} addOption={handleAddOption} />
        )}
      </ComboboxContent>
    </Combobox>
  );
};

export function getDropdownStyle(color?: string | null) {
  if (!color) return;

  return {
    backgroundColor: color,
    color: getTextColor(color),
  };
}
