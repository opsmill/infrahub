import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import DateTimePicker from "react-datepicker";

import { Col, Row } from "@/shared/components/container";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";
import { DATE_TIME_FORMAT } from "@/shared/utils/date";

import { isMetadataDatetimeFilter } from "@/entities/nodes/object/domain/metadata-filter-definitions";
import {
  FILTER_CONDITION,
  type FilterCondition,
  FilterConditionSelect,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export interface MetadataFilterFormProps {
  metadataFilter: AttributeSchema | RelationshipSchema;
  onSuccess?: () => void;
}

export function MetadataFilterForm({ metadataFilter, onSuccess }: MetadataFilterFormProps) {
  if (isMetadataDatetimeFilter(metadataFilter)) {
    return <MetadataDateFilterForm attributeSchema={metadataFilter} onSuccess={onSuccess} />;
  }

  return (
    <MetadataUserFilterForm
      relationshipSchema={metadataFilter as RelationshipSchema}
      onSuccess={onSuccess}
    />
  );
}

// ─── Date Filter ─────────────────────────────────────────────────────────────

interface MetadataDateFilterFormProps {
  attributeSchema: AttributeSchema;
  onSuccess?: () => void;
}

function getDefaultDateCondition(afterFilter?: Filter, beforeFilter?: Filter): FilterCondition {
  if (afterFilter && beforeFilter) return FILTER_CONDITION.BETWEEN;
  if (beforeFilter) return FILTER_CONDITION.BEFORE;
  return FILTER_CONDITION.AFTER;
}

function MetadataDateFilterForm({ attributeSchema, onSuccess }: MetadataDateFilterFormProps) {
  const [filters, setFilters] = useFilters();

  const afterFilterName = `${attributeSchema.name}__after`;
  const beforeFilterName = `${attributeSchema.name}__before`;

  const afterFilter = filters.find((f) => f.name === afterFilterName);
  const beforeFilter = filters.find((f) => f.name === beforeFilterName);

  const [condition, setCondition] = useState<FilterCondition>(
    getDefaultDateCondition(afterFilter, beforeFilter)
  );

  const toISOString = (value: unknown): string => {
    return value instanceof Date ? value.toISOString() : String(value);
  };

  const handleSubmit = (formData: Record<string, unknown>) => {
    const { afterDate, beforeDate } = formData;

    let newFilters = filters.filter(
      (f) => f.name !== afterFilterName && f.name !== beforeFilterName
    );

    if (condition === FILTER_CONDITION.AFTER && afterDate) {
      newFilters = [...newFilters, { name: afterFilterName, value: toISOString(afterDate) }];
    }

    if (condition === FILTER_CONDITION.BEFORE && beforeDate) {
      newFilters = [...newFilters, { name: beforeFilterName, value: toISOString(beforeDate) }];
    }

    if (condition === FILTER_CONDITION.BETWEEN) {
      if (afterDate) {
        newFilters = [...newFilters, { name: afterFilterName, value: toISOString(afterDate) }];
      }
      if (beforeDate) {
        newFilters = [...newFilters, { name: beforeFilterName, value: toISOString(beforeDate) }];
      }
    }

    setFilters(newFilters);
    onSuccess?.();
  };

  const isBetween = condition === FILTER_CONDITION.BETWEEN;
  const showAfter = condition === FILTER_CONDITION.AFTER || isBetween;
  const showBefore = condition === FILTER_CONDITION.BEFORE || isBetween;

  return (
    <Col className="p-2">
      <Row className="gap-0">
        <span className="font-semibold text-sm">Where</span>
        <FilterConditionSelect
          filterType="metadata-date"
          value={condition}
          onChange={(key) => setCondition(key as FilterCondition)}
        />
      </Row>

      <Form
        className="inline-flex flex-col gap-0 space-y-2"
        onSubmit={(formData) => handleSubmit(formData as Record<string, unknown>)}
        data-testid="metadata-date-filter-form"
      >
        <div className={isBetween ? "flex flex-row gap-4" : "flex flex-col gap-0"}>
          {showAfter && (
            <FormField
              name="afterDate"
              defaultValue={afterFilter?.value ?? undefined}
              render={({ field }) => (
                <div className="flex flex-col gap-1">
                  {isBetween && <span className="text-gray-600 text-xs">After</span>}
                  <DateTimePicker
                    selected={field.value ? new Date(field.value as string) : null}
                    onChange={field.onChange}
                    inline
                    showTimeSelect
                    timeIntervals={1}
                    calendarStartDay={1}
                    dateFormat={DATE_TIME_FORMAT}
                    calendarClassName="flex!"
                  />
                </div>
              )}
            />
          )}

          {showBefore && (
            <FormField
              name="beforeDate"
              defaultValue={beforeFilter?.value ?? undefined}
              render={({ field }) => (
                <div className="flex flex-col gap-1">
                  {isBetween && <span className="text-gray-600 text-xs">Before</span>}
                  <DateTimePicker
                    selected={field.value ? new Date(field.value as string) : null}
                    onChange={field.onChange}
                    inline
                    showTimeSelect
                    timeIntervals={1}
                    calendarStartDay={1}
                    dateFormat={DATE_TIME_FORMAT}
                    calendarClassName="flex!"
                  />
                </div>
              )}
            />
          )}
        </div>

        <FormSubmit className="self-end">Apply</FormSubmit>
      </Form>
    </Col>
  );
}

// ─── User Filter ─────────────────────────────────────────────────────────────

interface MetadataUserFilterFormProps {
  relationshipSchema: RelationshipSchema;
  onSuccess?: () => void;
}

type UserFormData = {
  relationships: RelationshipNode[];
};

function MetadataUserFilterForm({ relationshipSchema, onSuccess }: MetadataUserFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const currentFilter = filters.find((filter) => filter.name.startsWith(relationshipSchema.name));

  const handleSubmit = (data: UserFormData) => {
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
    }
    return setFilters([...filters, newFilter]);
  };

  return (
    <Col className="p-2">
      <Row className="gap-0">
        <span className="font-semibold text-sm">Where</span>
        <FilterConditionSelect
          filterType="metadata-relationship"
          value={FILTER_CONDITION.IS_ANY_OF}
          onChange={() => {}}
        />
      </Row>

      <Form
        className="inline-flex flex-col gap-0 space-y-2"
        onSubmit={(formData) => {
          handleSubmit(formData as UserFormData);
          onSuccess?.();
        }}
        data-testid="metadata-user-filter-form"
      >
        <FormField
          name="relationships"
          defaultValue={currentFilter?.value ?? undefined}
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

        <FormSubmit className="self-end">Apply</FormSubmit>
      </Form>
    </Col>
  );
}
