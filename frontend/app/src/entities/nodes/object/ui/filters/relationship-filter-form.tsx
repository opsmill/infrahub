import {
  FilterCondition,
  FilterConditionSelect,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { RelationshipSchema } from "@/entities/schema/types";
import { Button } from "@/shared/components/buttons/button-primitive";
import { getCurrentFilterCondition } from "@/shared/components/filters/utils/get-current-filter-condition";
import { Badge } from "@/shared/components/ui/badge";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import useFilters, { Filter } from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

export interface RelationshipFilterFormProps {
  relationshipSchema: RelationshipSchema;
  onSuccess?: () => void;
}

type FormData = {
  relationships: RelationshipNode[];
};

export function RelationshipFilterForm({
  relationshipSchema,
  onSuccess,
}: RelationshipFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const currentFilter = filters.find((filter) => filter.name.startsWith(relationshipSchema.name));
  const [condition, setCondition] = useState<FilterCondition | undefined>(
    getCurrentFilterCondition(currentFilter) ?? "is any of"
  );

  const handleSubmit = (data: FormData) => {
    const { relationships } = data;

    if (condition === "is empty") {
      return setFilters([
        ...filters.filter((f) => f.name !== currentFilter?.name),
        {
          name: `${relationshipSchema.name}__isnull`,
          value: true,
        },
      ]);
    }

    if (condition === "is not empty") {
      return setFilters([
        ...filters.filter((f) => f.name !== currentFilter?.name),
        {
          name: `${relationshipSchema.name}__isnull`,
          value: false,
        },
      ]);
    }

    if (condition === "is any of") {
      if (!relationships?.length) {
        return setFilters(filters.filter((f) => !f.name.startsWith(relationshipSchema.name)));
      }

      const newFilter: Filter = {
        name: `${relationshipSchema.name}__ids`,
        value: relationships,
      };

      if (currentFilter) {
        setFilters(
          filters.map((f) => (f.name.startsWith(relationshipSchema.name) ? newFilter : f))
        );
      } else {
        setFilters([...filters, newFilter]);
      }
    }
  };

  return (
    <div className="flex gap-2 p-2">
      <div className="h-10 inline-flex items-center">Where</div>

      <FilterConditionSelect
        selectedKey={condition}
        onSelectionChange={(key) => setCondition(key as FilterCondition)}
      />

      <Form
        className="space-y-0 flex gap-2"
        onSubmit={(formData) => {
          handleSubmit(formData as FormData);
          onSuccess?.();
        }}
      >
        {condition === "is any of" && (
          <FormField
            name="relationships"
            render={({ field }) => {
              const value = field.value as RelationshipNode[] | undefined;

              return (
                <Combobox defaultOpen>
                  <PopoverTrigger asChild>
                    <div
                      className={classNames(
                        inputStyle,
                        "has-[>:last-child:focus]:outline-none has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25  has-[>:last-child:focus]:border-custom-blue-600",
                        "cursor-pointer min-w-[132px] max-w-[300px]"
                      )}
                    >
                      <div className="flex-grow flex flex-wrap gap-2">
                        {value?.map(({ id, display_label }) => (
                          <Badge key={id} className="flex items-center gap-1 pr-0.5">
                            {display_label}

                            <Button
                              size="icon"
                              variant="ghost"
                              onClick={(e) => {
                                e.stopPropagation();
                                field.onChange(value.filter((item) => item.id !== id));
                              }}
                              className="text-gray-500 hover:text-gray-800 h-4 w-4"
                              aria-label="Remove"
                              data-testid="remove-option"
                            >
                              &times;
                            </Button>
                          </Badge>
                        ))}
                      </div>

                      <button type="button" className="text-gray-600 outline-none w-3.5 h-3.5">
                        <Icon icon="mdi:unfold-more-horizontal" />
                      </button>
                    </div>
                  </PopoverTrigger>

                  <ComboboxContent fitTriggerWidth={false}>
                    <RelationshipComboboxList
                      peer={relationshipSchema.peer}
                      onSelect={(relationship) => {
                        field.onChange(value ? [...value, relationship] : [relationship]);
                      }}
                      filterItem={(node) => !value?.some((v) => v.id === node.id)}
                    />
                  </ComboboxContent>
                </Combobox>
              );
            }}
          />
        )}

        <FormSubmit>Apply</FormSubmit>
      </Form>
    </div>
  );
}
