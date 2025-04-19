import { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import { Button } from "@/shared/components/buttons/button-primitive";
import { FilterKindSelector } from "@/shared/components/filters/filter-kind-selector";
import { getObjectFromFilters } from "@/shared/components/filters/utils/getObjectFromFilters";
import { DynamicInput } from "@/shared/components/form/dynamic-form";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { Form, FormProps, FormRef, FormSubmit } from "@/shared/components/ui/form";
import { Filter } from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";
import { forwardRef } from "react";

export interface FilterFormProps extends FormProps {
  schema: ModelSchema | null;
  filters: Array<Filter>;
  onCancel?: () => void;
}

export const FilterForm = forwardRef<FormRef, FilterFormProps>(
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
        className={classNames("bg-white flex flex-col flex-1 overflow-auto p-4", className)}
        {...props}
      >
        {isGenericSchema(schema) && schema.used_by?.length ? (
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
