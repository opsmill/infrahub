import React, { forwardRef, useState } from "react";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { Button } from "@/components/buttons/button-primitive";
import { useMutation } from "@/hooks/useQuery";
import ModalDelete from "@/components/modals/modal-delete";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import DynamicForm from "@/components/form/dynamic-form";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { ENUM_ADD_MUTATION, ENUM_REMOVE_MUTATION } from "@/graphql/mutations/schema/enum";

export interface EnumItemProps extends React.ComponentPropsWithoutRef<typeof CommandItem> {
  fieldSchema: {
    name: string;
  };
  currentValue: unknown | null;
  schema: IModelSchema;
  onDelete: (id: unknown) => void;
  item: unknown;
}

export const EnumItem = React.forwardRef<React.ElementRef<typeof CommandItem>, EnumItemProps>(
  (
    { fieldSchema, currentValue, schema, onDelete, className, value, children, item, ...props },
    ref
  ) => {
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [removeEnum, { loading }] = useMutation(ENUM_REMOVE_MUTATION, {
      variables: { kind: schema.kind, attribute: fieldSchema.name, enum: item },
    });

    const handleDelete = async () => {
      try {
        await removeEnum();
        onDelete(item);
      } catch (error) {
        console.error("Error deleting enum:", error);
      }
    };

    return (
      <>
        <CommandItem ref={ref} {...props}>
          <Icon icon="mdi:check" className={classNames(currentValue !== item && "opacity-0")} />
          {item?.toString()}
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
        </CommandItem>

        <ModalDelete
          title="Delete"
          description={
            <>
              Are you sure you want to delete the enum{" "}
              <span className="font-semibold text-gray-800">{item?.toString()}</span>?
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
    <div className="p-2">
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
  ({ items, value, fieldSchema, schema, className, onChange, ...props }, ref) => {
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
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger ref={ref} asChild>
          <button
            type="button"
            role="combobox"
            className={classNames(
              "h-10 flex items-center w-full rounded-md border border-gray-300 bg-white p-2 text-sm placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-custom-blue-600 focus-visible:border-custom-blue-600 disabled:cursor-not-allowed disabled:bg-gray-100",
              className
            )}
            {...props}>
            {value}
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
              <CommandEmpty>No enum found.</CommandEmpty>
              {localItems.map((item) => (
                <EnumItem
                  key={item?.toString()}
                  item={item}
                  currentValue={value}
                  schema={schema}
                  fieldSchema={fieldSchema}
                  onSelect={() => {
                    onChange(item === value ? null : item);
                    setOpen(false);
                  }}
                  onDelete={handleDeleteOption}
                />
              ))}
            </CommandList>
          </Command>

          <EnumAddAction schema={schema} field={fieldSchema} addOption={handleAddOption} />
        </PopoverContent>
      </Popover>
    );
  }
);
