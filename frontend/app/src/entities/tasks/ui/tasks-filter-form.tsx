import { useAtomValue } from "jotai";
import { forwardRef } from "react";

import { Button } from "@/shared/components/buttons/button-primitive";
import { getObjectFromFilters } from "@/shared/components/filters/utils/getObjectFromFilters";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import { Form, type FormProps, type FormRef, FormSubmit } from "@/shared/components/ui/form";
import type { Filter } from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

import { branchesState } from "@/entities/branches/stores";
import { TASK_STATES } from "@/entities/tasks/constants";

export interface FilterFormProps extends FormProps {
  filters: Array<Filter>;
  onCancel?: () => void;
}

export const TasksFilterForm = forwardRef<FormRef, FilterFormProps>(
  ({ filters, className, onSubmit, onCancel, ...props }, ref) => {
    const branches = useAtomValue(branchesState);

    const currentFilters = getObjectFromFilters(null, filters);

    const branchesOptions = branches.map((branch) => ({
      value: branch.name,
      label: branch.name,
    }));

    const statesOptions = TASK_STATES.map((state) => ({
      value: state,
      label: state,
    }));

    return (
      <Form
        ref={ref}
        onSubmit={onSubmit}
        className={classNames("flex flex-1 flex-col overflow-auto bg-white p-4", className)}
        defaultValues={{
          branch: currentFilters?.branch,
          state: currentFilters?.state,
        }}
        {...props}
      >
        <DropdownField name="branch" label="Branch" items={branchesOptions} />

        <DropdownField name="state" label="State" items={statesOptions} />

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
