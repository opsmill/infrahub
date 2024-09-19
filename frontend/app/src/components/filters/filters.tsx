import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import { SEARCH_FILTERS } from "@/config/constants";
import useFilters, { Filter } from "@/hooks/useFilters";
import { Icon } from "@iconify-icon/react";
import React, { forwardRef, useState } from "react";
import usePagination from "@/hooks/usePagination";
import { iGenericSchema, IModelSchema, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { getFiltersFromFormData } from "@/components/filters/utils/getFiltersFromFormData";
import { FormFieldValue } from "@/components/form/type";
import {
  Form,
  FormField,
  FormInput,
  FormMessage,
  FormProps,
  FormRef,
  FormSubmit,
} from "@/components/ui/form";
import { DynamicInput } from "@/components/form/dynamic-form";
import { getFormFieldsFromSchema } from "@/components/form/utils/getFormFieldsFromSchema";
import { Button, ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { classNames, isGeneric } from "@/utils/common";
import { useAtomValue } from "jotai";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/components/ui/combobox3";
import { DEFAULT_FORM_FIELD_VALUE } from "@/components/form/constants";
import { LabelFormField } from "@/components/form/fields/common";
import { Badge } from "@/components/ui/badge";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";
import { getObjectFromFilters } from "@/components/filters/utils/getObjectFromFilters";

type FiltersProps = {
  schema: IModelSchema;
};

export const Filters = ({ schema }: FiltersProps) => {
  const [filters, setFilters] = useFilters();
  const [pagination, setPagination] = usePagination();
  const [showFilters, setShowFilters] = useState(false);

  const removeFilters = () => {
    const newFilters = filters.filter((filter) => SEARCH_FILTERS.includes(filter.name));

    setPagination({
      ...pagination,
      offset: 0,
    });

    setFilters(newFilters);
  };

  const handleSubmit = (formData: Record<string, FormFieldValue>) => {
    const newFilters = getFiltersFromFormData(formData);

    setPagination({
      ...pagination,
      offset: 0,
    });

    setFilters(newFilters);

    setShowFilters(false);
  };

  const currentFilters = filters.filter((filter) => !SEARCH_FILTERS.includes(filter.name));

  return (
    <>
      <div className="flex-grow flex items-center gap-1">
        <ButtonWithTooltip
          tooltipEnabled
          tooltipContent="Apply filters"
          variant="ghost"
          size="icon"
          data-testid="apply-filters"
          onClick={() => setShowFilters(true)}>
          <Icon icon={"mdi:filter-outline"} className="text-custom-blue-100" />
        </ButtonWithTooltip>

        <span className="text-xs">Filters: {currentFilters.length}</span>

        {!!currentFilters.length && (
          <Button onClick={removeFilters} variant="ghost" size="icon" data-testid="remove-filters">
            <Icon icon="mdi:close" className="text-gray-400" />
          </Button>
        )}
      </div>

      <SlideOver
        title={<SlideOverTitle schema={schema} currentObjectLabel="All" title="Apply filters" />}
        open={showFilters}
        setOpen={setShowFilters}>
        <FilterForm
          filters={filters}
          schema={schema}
          onSubmit={handleSubmit}
          onCancel={() => setShowFilters(false)}
        />
      </SlideOver>
    </>
  );
};

export interface FilterFormProps extends FormProps {
  schema: IModelSchema;
  filters: Array<Filter>;
  onCancel?: () => void;
}

const FilterForm = forwardRef<FormRef, FilterFormProps>(
  ({ filters, className, schema, onSubmit, onCancel, ...props }, ref) => {
    const fields = getFormFieldsFromSchema({
      schema,
      isFilterForm: true,
      initialObject: getObjectFromFilters(schema, filters),
    });

    return (
      <Form
        ref={ref}
        onSubmit={onSubmit}
        className={classNames("bg-custom-white flex flex-col flex-1 overflow-auto p-4", className)}
        {...props}>
        {isGeneric(schema) && schema.used_by?.length ? (
          <FilterKindSelector genericSchema={schema} />
        ) : null}

        {fields.map((field) => (
          <DynamicInput key={field.name} {...field} />
        ))}

        <div className="text-right">
          {onCancel && (
            <Button variant="outline" className="mr-2" onClick={onCancel}>
              Cancel
            </Button>
          )}

          <FormSubmit>Apply filters</FormSubmit>
        </div>
      </Form>
    );
  }
);

const FilterKindSelector = ({ genericSchema }: { genericSchema: iGenericSchema }) => {
  const [activeFilters] = useFilters();
  const availableNodes = useAtomValue(schemaState);
  const availableProfiles = useAtomValue(profilesAtom);
  const allAvailableSchemas = [...availableNodes, ...availableProfiles];

  const selectedKindFilter = activeFilters.find((filter) => filter.name == "kind__value");
  const compatibleSchemas = (genericSchema.used_by ?? [])
    .map((kindValue) => {
      if (!allAvailableSchemas) return null;

      return allAvailableSchemas.find((schema) => schema.kind === kindValue);
    })
    .filter((schema) => !!schema);

  return (
    <FormField
      name="kind"
      defaultValue={
        selectedKindFilter
          ? { source: { type: "user" }, value: selectedKindFilter.value }
          : DEFAULT_FORM_FIELD_VALUE
      }
      render={({ field }) => {
        const [isDropdownOpen, setIsDropdownOpen] = useState(false);
        const currentFieldValue = field.value;
        const selectedSchema = allAvailableSchemas.find(
          (schema) => schema.kind === currentFieldValue?.value
        );

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField
              label="Kind"
              description="Select a kind to filter nodes"
              fieldData={currentFieldValue}
            />

            <Combobox open={isDropdownOpen} onOpenChange={setIsDropdownOpen}>
              <FormInput>
                <ComboboxTrigger>
                  {selectedSchema && (
                    <div className="w-full flex justify-between">
                      {selectedSchema.label} <Badge>{selectedSchema.namespace}</Badge>
                    </div>
                  )}
                </ComboboxTrigger>
              </FormInput>

              <ComboboxContent>
                <ComboboxList>
                  {compatibleSchemas.map((schemaOption) => (
                    <ComboboxItem
                      key={schemaOption.kind}
                      selectedValue={selectedSchema?.kind}
                      value={schemaOption.kind!}
                      onSelect={() => {
                        const newSelectedValue =
                          schemaOption.kind === selectedSchema?.kind ? null : schemaOption.kind;
                        field.onChange(
                          updateFormFieldValue(newSelectedValue ?? null, DEFAULT_FORM_FIELD_VALUE)
                        );
                        setIsDropdownOpen(false);
                      }}>
                      {schemaOption.label}{" "}
                      <Badge className="ml-auto">{schemaOption?.namespace}</Badge>
                    </ComboboxItem>
                  ))}
                </ComboboxList>
              </ComboboxContent>
            </Combobox>

            <FormMessage />
          </div>
        );
      }}
    />
  );
};
