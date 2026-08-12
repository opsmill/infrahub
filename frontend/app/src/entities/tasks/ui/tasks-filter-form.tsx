import { Button } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import type React from "react";

import { Row } from "@/shared/components/container";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import { Form, type FormProps, type FormRef, FormSubmit } from "@/shared/components/ui/form";

import { branchesState } from "@/entities/branches/stores";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { getObjectFromFilters } from "@/entities/nodes/filters/domain/rules/getObjectFromFilters";
import { TASK_STATES } from "@/entities/tasks/domain/model/task";

export interface FilterFormProps extends FormProps {
  ref?: React.Ref<FormRef>;
  filters: Array<Filter>;
  onCancel?: () => void;
}

export const TasksFilterForm = ({
  ref,
  filters,
  className,
  onSubmit,
  onCancel,
  ...props
}: FilterFormProps) => {
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
      className={className}
      defaultValues={{
        branch: currentFilters?.branch,
        state: currentFilters?.state,
      }}
      {...props}
    >
      <DropdownField name="branch" label="Branch" items={branchesOptions} />

      <DropdownField name="state" label="State" items={statesOptions} />

      <Row className="justify-end">
        {onCancel && (
          <Button variant="outline" onPress={onCancel}>
            Cancel
          </Button>
        )}

        <FormSubmit>Apply filters</FormSubmit>
      </Row>
    </Form>
  );
};
