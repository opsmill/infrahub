import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { Button } from "@/shared/components/buttons/button-primitive";
import { getCurrentFilterCondition } from "@/shared/components/filters/utils/get-current-filter-condition";
import { Badge } from "@/shared/components/ui/badge";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

import {
  FILTER_CONDITION,
  type FilterCondition,
  FilterConditionSelect,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import type { RelationshipSchema } from "@/entities/schema/types";

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
  const [condition, setCondition] = useState<FilterCondition>(
    getCurrentFilterCondition(currentFilter) ?? FILTER_CONDITION.IS_ANY_OF
  );

  const handleSubmit = (data: FormData) => {
    if (condition === FILTER_CONDITION.IS_EMPTY) {
      return setFilters([
        ...filters.filter((f) => f.name !== currentFilter?.name),
        {
          name: `${relationshipSchema.name}__isnull`,
          value: true,
        },
      ]);
    }

    if (condition === FILTER_CONDITION.IS_NOT_EMPTY) {
      return setFilters([
        ...filters.filter((f) => f.name !== currentFilter?.name),
        {
          name: `${relationshipSchema.name}__isnull`,
          value: false,
        },
      ]);
    }

    if (condition === FILTER_CONDITION.IS_ANY_OF) {
      const { relationships } = data;

      if (!relationships?.length) {
        return setFilters(filters.filter((f) => !f.name.startsWith(relationshipSchema.name)));
      }

      const newFilter: Filter = {
        name: `${relationshipSchema.name}__ids`,
        value: relationships,
      };

      if (currentFilter) {
        return setFilters(
          filters.map((f) => (f.name.startsWith(relationshipSchema.name) ? newFilter : f))
        );
      } else {
        return setFilters([...filters, newFilter]);
      }
    }
  };

  return (
    <div className="flex gap-2 p-2">
      <div className="inline-flex h-10 items-center">Where</div>

      <FilterConditionSelect
        filterType="relationship"
        value={condition}
        onChange={(key) => setCondition(key as FilterCondition)}
      />

      <Form
        className="flex gap-2 space-y-0"
        onSubmit={(formData) => {
          handleSubmit(formData as FormData);
          onSuccess?.();
        }}
        data-testid="relationship-filter-form"
      >
        {condition === FILTER_CONDITION.IS_ANY_OF && (
          <FormField
            name="relationships"
            defaultValue={
              currentFilter &&
              getCurrentFilterCondition(currentFilter) === FILTER_CONDITION.IS_ANY_OF
                ? currentFilter.value
                : undefined
            }
            render={({ field }) => {
              const value = field.value as RelationshipNode[] | undefined;

              return (
                <Combobox defaultOpen>
                  <PopoverTrigger asChild>
                    <div
                      className={classNames(
                        inputStyle,
                        "has-[>:last-child:focus]:border-custom-blue-600 has-[>:last-child:focus]:outline-hidden has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25",
                        "min-w-[132px] max-w-[300px] cursor-pointer"
                      )}
                    >
                      <div className="flex grow flex-wrap gap-2">
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
                              className="h-4 w-4 text-gray-500 hover:text-gray-800"
                              aria-label="Remove"
                              data-testid="remove-option"
                            >
                              &times;
                            </Button>
                          </Badge>
                        ))}
                      </div>

                      <button type="button" className="h-3.5 w-3.5 text-gray-600 outline-hidden">
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
