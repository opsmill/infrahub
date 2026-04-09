import { useState } from "react";

import { Col, Row } from "@/shared/components/container";
import { getCurrentFilterCondition } from "@/shared/components/filters/utils/get-current-filter-condition";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";

import { DynamicFilterInput } from "@/entities/nodes/object/ui/filters/dynamic-filter-input";
import {
  FILTER_CONDITION,
  type FilterCondition,
  FilterConditionSelect,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeSchema } from "@/entities/schema/types";

export type AttributeFilterFormProps = {
  attributeSchema: AttributeSchema;
  onSuccess?: () => void;
};

export function AttributeFilterForm({ attributeSchema, onSuccess }: AttributeFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const currentFilter = filters.find((filter) => filter.name.startsWith(attributeSchema.name));
  const isDatetime = attributeSchema.kind === ATTRIBUTE_KIND.DATETIME;
  const defaultCondition = isDatetime ? FILTER_CONDITION.IS_EMPTY : FILTER_CONDITION.CONTAINS;
  const [condition, setCondition] = useState<FilterCondition>(
    getCurrentFilterCondition(currentFilter) ?? defaultCondition
  );

  const handleSubmit = (formData: Record<string, FormAttributeValue["value"]>) => {
    if (condition === FILTER_CONDITION.CONTAINS) {
      const { attribute } = formData;

      if (!attribute && attribute !== 0 && attribute !== false) {
        return setFilters(filters.filter((f) => !f.name.startsWith(attributeSchema.name)));
      }

      const isAttributeArray = Array.isArray(attribute);
      const newFilter: Filter = {
        name: `${attributeSchema.name}__${isAttributeArray ? "values" : "value"}`,
        value: attribute,
      };

      if (currentFilter) {
        return setFilters(
          filters.map((f) => (f.name.startsWith(attributeSchema.name) ? newFilter : f))
        );
      } else {
        return setFilters([...filters, newFilter]);
      }
    }

    if (condition === FILTER_CONDITION.IS_EMPTY) {
      return setFilters([
        ...filters.filter((f) => f.name !== currentFilter?.name),
        {
          name: `${attributeSchema.name}__isnull`,
          value: true,
        },
      ]);
    }

    if (condition === FILTER_CONDITION.IS_NOT_EMPTY) {
      return setFilters([
        ...filters.filter((f) => f.name !== currentFilter?.name),
        {
          name: `${attributeSchema.name}__isnull`,
          value: false,
        },
      ]);
    }
  };

  const showInput = condition === FILTER_CONDITION.CONTAINS;

  return (
    <Col className="p-2">
      <Row className="gap-0">
        <span className="font-semibold text-sm">Where</span>
        <FilterConditionSelect
          filterType={isDatetime ? "datetime" : "attribute"}
          value={condition}
          onChange={(key) => setCondition(key as FilterCondition)}
        />
      </Row>

      <Form
        onSubmit={(formData) => {
          handleSubmit(formData);
          onSuccess?.();
        }}
        data-testid="attribute-filter-form"
        className="inline-flex flex-col gap-0 space-y-2"
      >
        {showInput && (
          <FormField
            name="attribute"
            defaultValue={
              currentFilter && getCurrentFilterCondition(currentFilter) === condition
                ? currentFilter.value
                : undefined
            }
            render={({ field }) => {
              return <DynamicFilterInput {...field} fieldSchema={attributeSchema} />;
            }}
          />
        )}

        <FormSubmit className="self-end">Apply</FormSubmit>
      </Form>
    </Col>
  );
}
