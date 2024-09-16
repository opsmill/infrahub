import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { classNames, getTextColor } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import React, { forwardRef, HTMLAttributes, useState } from "react";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Button } from "@/components/buttons/button-primitive";
import { useMutation } from "@/hooks/useQuery";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { AttributeSchema } from "@/screens/schema/types";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import DynamicForm from "@/components/form/dynamic-form";
import { Badge } from "@/components/ui/badge";
import {
  DROPDOWN_ADD_MUTATION,
  DROPDOWN_REMOVE_MUTATION,
} from "@/graphql/mutations/schema/dropdown";
import { isRequired } from "@/components/form/utils/validation";
import ModalDelete from "@/components/modals/modal-delete";

export type DropdownOption = {
  value: string;
  label: string;
  color?: string;
  description?: string;
};

export interface DropdownProps extends Omit<HTMLAttributes<HTMLButtonElement>, "onChange"> {
  value?: DropdownOption["value"] | null;
  items: Array<DropdownOption>;
  className?: string;
  onChange: (value: DropdownOption["value"] | null) => void;
  schema?: IModelSchema;
  field?: AttributeSchema;
}

export interface DropdownItemProps extends React.ComponentPropsWithoutRef<typeof CommandItem> {
  fieldSchema?: {
    name: string;
  };
  currentValue: DropdownProps["value"];
  schema?: IModelSchema;
  onDelete: (item: DropdownOption) => void;
  item: DropdownOption;
}

export const DropdownItem = React.forwardRef<
  React.ElementRef<typeof CommandItem>,
  DropdownItemProps
>(
  (
    {
      fieldSchema,
      currentValue,
      schema,
      onDelete,
      className,
      value,
      children,
      style,
      item,
      ...props
    },
    ref
  ) => {
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [removeDropdownOption, { loading }] = useMutation(DROPDOWN_REMOVE_MUTATION);

    return (
      <CommandItem ref={ref} className={classNames("rounded-none", className)} {...props}>
        <Icon icon="mdi:check" className={classNames(currentValue !== item.value && "opacity-0")} />

        <div className="overflow-hidden">
          <Badge
            className="font-medium"
            style={
              item?.color
                ? {
                    backgroundColor: item.color,
                    color: getTextColor(item.color),
                  }
                : undefined
            }>
            {item.label}
          </Badge>
          <p className="text-xs truncate">{item.description}</p>
        </div>

        {schema && fieldSchema && (
          <>
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
                    }>
                    {item.label}
                  </Badge>{" "}
                  ?
                </>
              }
              setOpen={setShowDeleteModal}
              onCancel={() => setShowDeleteModal(false)}
              onDelete={async () => {
                try {
                  await removeDropdownOption({
                    variables: {
                      kind: schema.kind,
                      attribute: fieldSchema.name,
                      dropdown: item.value,
                    },
                  });
                  onDelete(item);
                } catch (error) {
                  console.error("Error deleting dropdown item:", error);
                }
              }}
              open={showDeleteModal}
              isLoading={loading}
            />
          </>
        )}
      </CommandItem>
    );
  }
);

interface DropdownAddActionProps {
  schema: IModelSchema;
  field: AttributeSchema;
  addOption: (item: DropdownOption) => void;
}

export const DropdownAddAction: React.FC<DropdownAddActionProps> = ({
  schema,
  field,
  addOption,
}) => {
  const [open, setOpen] = useState(false);
  const [addDropdownItem] = useMutation(DROPDOWN_ADD_MUTATION);

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
            currentObjectLabel={field?.label ?? ""}
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
            const { data } = await addDropdownItem({
              variables: {
                kind: schema.kind,
                attribute: field.name,
                dropdown: formData.value.value,
                label: formData.label?.value,
                color: formData.color?.value,
                description: formData.description?.value,
              },
            });
            if (data?.SchemaDropdownAdd?.ok) {
              addOption(data?.SchemaDropdownAdd?.object);
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

export const Dropdown = forwardRef<HTMLButtonElement, DropdownProps>(
  ({ className, items, onChange, value, schema, field, ...props }, ref) => {
    const [localItems, setLocalItems] = useState(items);
    const [open, setOpen] = useState(false);

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
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild ref={ref} {...props}>
          <button
            type="button"
            role="combobox"
            className={classNames(
              "h-10 flex items-center w-full rounded-md border border-gray-300 bg-white p-2 text-sm placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-custom-blue-600 focus-visible:border-custom-blue-600 disabled:cursor-not-allowed disabled:bg-gray-100",
              className
            )}
            style={
              selectItem?.color
                ? {
                    backgroundColor: selectItem.color,
                    color: getTextColor(selectItem.color),
                  }
                : undefined
            }>
            {selectItem?.label}
            <Icon icon="mdi:unfold-more-horizontal" className="ml-auto text-gray-600" />
          </button>
        </PopoverTrigger>

        <PopoverContent className="p-0" portal={false}>
          <Command
            style={{
              width: "var(--radix-popover-trigger-width)",
              maxHeight: "min(var(--radix-popover-content-available-height), 300px)",
            }}>
            <CommandInput placeholder="Filter..." />

            <CommandList>
              <CommandEmpty>No dropdown found.</CommandEmpty>

              {localItems.map((item) => (
                <DropdownItem
                  key={item.value}
                  schema={schema}
                  fieldSchema={field}
                  currentValue={selectItem?.value}
                  onSelect={() => {
                    onChange(item.value === value ? null : item.value);
                    setOpen(false);
                  }}
                  item={item}
                  onDelete={handleDeleteOption}
                />
              ))}
            </CommandList>
          </Command>

          {schema && field && (
            <DropdownAddAction schema={schema} field={field} addOption={handleAddOption} />
          )}
        </PopoverContent>
      </Popover>
    );
  }
);
