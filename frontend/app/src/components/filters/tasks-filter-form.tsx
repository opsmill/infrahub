import { Button } from "@/components/buttons/button-primitive";
import { Form, FormProps, FormRef, FormSubmit } from "@/components/ui/form";
import { Filter } from "@/hooks/useFilters";
import { TASK_STATES } from "@/screens/tasks/constants";
import { branchesState } from "@/state/atoms/branches.atom";
import { classNames } from "@/utils/common";
import { useAtomValue } from "jotai";
import { forwardRef } from "react";
import DropdownField from "../form/fields/dropdown.field";
import { getObjectFromFilters } from "./utils/getObjectFromFilters";

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
        className={classNames("bg-custom-white flex flex-col flex-1 overflow-auto p-4", className)}
        {...props}
      >
        <DropdownField
          name="branch"
          label="Branch"
          items={branchesOptions}
          defaultValue={currentFilters?.branch}
        />

        <DropdownField
          name="state"
          label="State"
          items={statesOptions}
          defaultValue={currentFilters?.state}
        />

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
