import { Button } from "@infrahub/ui";
import { useState } from "react";
import { type FieldValues, useForm, useWatch } from "react-hook-form";

import { Row } from "@/shared/components/container";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import InputField from "@/shared/components/form/fields/input.field";
import type { ObjectFormProps } from "@/shared/components/form/object-form";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import type { NumberPoolForEditing } from "@/entities/resource-manager/domain/model/number-pool";
import { EMPTY_RANGE_ROW } from "@/entities/resource-manager/domain/model/number-pool-range";
import {
  NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
  NUMBER_POOL_NODE_FIELD,
  NUMBER_POOL_RANGES_FIELD,
} from "@/entities/resource-manager/domain/model/pool";
import { toRangeRows } from "@/entities/resource-manager/domain/rules/plan-range-changes";
import type { RangeLimits } from "@/entities/resource-manager/domain/rules/validate-range-rows";
import { useSaveNumberPool } from "@/entities/resource-manager/ui/hooks/use-save-number-pool";
import { AllocatesBlock } from "@/entities/resource-manager/ui/number-pool-form/allocates-block";
import {
  RangesField,
  ReadOnlyRangesField,
} from "@/entities/resource-manager/ui/number-pool-form/ranges-field";
import { useGetNumberPoolForEditing } from "@/entities/resource-manager/ui/queries/get-number-pool-for-editing.query";
import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface NumberPoolFormProps {
  currentObject?: ObjectFormProps["currentObject"];
  onCancel?: ObjectFormProps["onCancel"];
  onSuccess?: ObjectFormProps["onSuccess"];
}

function useRangeLimits(kind?: string, attributeName?: string): RangeLimits | null {
  const { schema } = useSchema(kind);
  const attribute = schema?.attributes?.find(({ name }) => name === attributeName);
  if (attribute?.kind !== ATTRIBUTE_KIND.NUMBER) return null;

  const { min_value, max_value } = attribute.parameters ?? {};
  return { attribute: attribute.name, min: min_value, max: max_value };
}

function toFieldValue(value: string) {
  return value ? { source: { type: "user" }, value } : DEFAULT_FORM_FIELD_VALUE;
}

export const NumberPoolForm = ({ currentObject, ...props }: NumberPoolFormProps) => {
  const poolId = typeof currentObject?.id === "string" ? currentObject.id : "";
  const [mountedAt] = useState(() => Date.now());
  const { data, dataUpdatedAt, isFetchedAfterMount } = useGetNumberPoolForEditing(
    { poolId },
    { enabled: !!poolId, refetchOnMount: "always" }
  );
  // The rows are diffed against the stored ranges on save, so they must start from a read made after opening, not the cache.
  const initialPool = dataUpdatedAt >= mountedAt ? data : undefined;

  if (!poolId) return <NumberPoolFormContent {...props} />;
  if (initialPool) return <NumberPoolFormContent initialPool={initialPool} {...props} />;
  if (isFetchedAfterMount) {
    return <Alert type={ALERT_TYPES.ERROR} message="Unable to load the number pool" />;
  }

  return <LoadingIndicator className="p-4" />;
};

interface NumberPoolFormContentProps extends Omit<NumberPoolFormProps, "currentObject"> {
  initialPool?: NumberPoolForEditing;
}

const NumberPoolFormContent = ({
  initialPool,
  onSuccess,
  onCancel,
}: NumberPoolFormContentProps) => {
  const { poolId, saveError, save } = useSaveNumberPool({ initialPool, onSuccess });
  const isSchemaPool = initialPool?.poolType === "Schema";
  const { data: storedPool } = useGetNumberPoolForEditing(
    { poolId: poolId ?? "" },
    { enabled: !!poolId }
  );

  // Default values are read once at mount, so a background refetch of the pool never resets the rows being typed.
  const form = useForm<FieldValues>({
    defaultValues: {
      name: initialPool ? toFieldValue(initialPool.name) : DEFAULT_FORM_FIELD_VALUE,
      description: initialPool ? toFieldValue(initialPool.description) : DEFAULT_FORM_FIELD_VALUE,
      [NUMBER_POOL_RANGES_FIELD]: initialPool
        ? toRangeRows(initialPool.ranges)
        : [{ ...EMPTY_RANGE_ROW }],
    },
  });
  const [selectedNode, selectedAttribute]: Array<FormAttributeValue | undefined> = useWatch({
    control: form.control,
    name: [NUMBER_POOL_NODE_FIELD, NUMBER_POOL_NODE_ATTRIBUTE_FIELD],
  });
  const rangeLimits = useRangeLimits(
    storedPool?.node ?? selectedNode?.value?.toString(),
    storedPool?.nodeAttribute ?? selectedAttribute?.value?.toString()
  );

  return (
    <div className="flex flex-1 flex-col overflow-auto bg-content">
      <Form form={form} onSubmit={save}>
        <InputField name="name" label="Name" rules={{ required: true }} />
        <InputField name="description" label="Description" />

        {poolId ? (
          <AllocatesBlock
            variant="read-only"
            node={storedPool?.node ?? ""}
            attribute={storedPool?.nodeAttribute ?? ""}
            scope={storedPool?.allocationScope ?? []}
          />
        ) : (
          <AllocatesBlock variant="input" />
        )}

        {saveError && <Alert type={ALERT_TYPES.ERROR} message={saveError} />}
        {isSchemaPool ? (
          <ReadOnlyRangesField ranges={storedPool?.ranges ?? initialPool.ranges} />
        ) : (
          <RangesField limits={rangeLimits} />
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
    </div>
  );
};
