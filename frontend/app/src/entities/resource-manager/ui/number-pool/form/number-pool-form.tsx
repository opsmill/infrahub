import { Button } from "@infrahub/ui";
import { CircleXIcon } from "lucide-react";
import { type UseFormReturn, useFormState } from "react-hook-form";

import { Col, Row } from "@/shared/components/container";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { Form, FormField, FormInput, FormMessage, FormSubmit } from "@/shared/components/ui/form";
import { Input } from "@/shared/components/ui/input";

import type { NumberPoolData } from "@/entities/resource-manager/domain/model/number-pool";
import { NumberPoolAllocatesInput } from "@/entities/resource-manager/ui/number-pool/form/number-pool-allocates-input";
import { NumberPoolRangesInput } from "@/entities/resource-manager/ui/number-pool/form/number-pool-ranges-input";

export type NumberPoolFormData = Pick<
  NumberPoolData,
  "name" | "description" | "node" | "node_attribute" | "allocation_scope" | "ranges"
>;

export interface NumberPoolFormProps {
  form: UseFormReturn<NumberPoolFormData>;
  onSubmit: (values: NumberPoolFormData) => Promise<void>;
  onCancel?: () => void;
  isUpdate?: boolean;
}

export function NumberPoolForm({ form, onSubmit, onCancel, isUpdate }: NumberPoolFormProps) {
  const { errors } = useFormState({ control: form.control });
  const serverError = errors.root?.server?.message;

  return (
    <Form form={form} onSubmit={onSubmit} onCancel={onCancel}>
      <FormField
        name="name.value"
        rules={{ required: "Required" }}
        render={({ field }) => (
          <Col>
            <LabelFormField label="Name" required />
            <FormInput>
              <Input {...field} value={field.value ?? ""} />
            </FormInput>
            <FormMessage />
          </Col>
        )}
      />
      <FormField
        name="description.value"
        render={({ field }) => (
          <Col>
            <LabelFormField label="Description" />
            <FormInput>
              <Input {...field} value={field.value ?? ""} />
            </FormInput>
          </Col>
        )}
      />
      <NumberPoolAllocatesInput isReadOnly={isUpdate} />
      <NumberPoolRangesInput />

      {serverError && (
        <Row
          role="alert"
          className="items-start rounded-lg border border-danger bg-danger-surface px-2.5 py-2 text-danger text-sm"
        >
          <CircleXIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span className="text-pretty">{serverError}</span>
        </Row>
      )}

      <Row className="justify-end">
        {onCancel && (
          <Button variant="outline" onPress={onCancel}>
            Cancel
          </Button>
        )}
        <FormSubmit>Save</FormSubmit>
      </Row>
    </Form>
  );
}
