import { Button } from "@infrahub/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { type FieldValues, useForm, useWatch } from "react-hook-form";
import { toast } from "react-toastify";

import { Row } from "@/shared/components/container";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import InputField from "@/shared/components/form/fields/input.field";
import type { ObjectFormProps } from "@/shared/components/form/object-form";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import type {
  NumberPoolForEditing,
  RangeRow,
  StoredRange,
} from "@/entities/resource-manager/domain/model/number-pool-range";
import {
  NUMBER_POOL_ALLOCATION_SCOPE_FIELD,
  NUMBER_POOL_KIND,
  NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
  NUMBER_POOL_NODE_FIELD,
} from "@/entities/resource-manager/domain/model/pool";
import {
  diffRanges,
  hasRangeChanges,
  matchRowsToStored,
  toRangeRows,
} from "@/entities/resource-manager/domain/rules/plan-range-changes";
import type { RangeLimits } from "@/entities/resource-manager/domain/rules/validate-range-rows";
import { AllocatesBlock } from "@/entities/resource-manager/ui/number-pool-form/allocates-block";
import {
  EMPTY_RANGE_ROW,
  RANGES_FIELD,
  RangesField,
} from "@/entities/resource-manager/ui/number-pool-form/ranges-field";
import { ScopeField } from "@/entities/resource-manager/ui/number-pool-form/scope-field";
import { useApplyNumberPoolRangeChangesMutation } from "@/entities/resource-manager/ui/queries/apply-number-pool-range-changes.mutation";
import {
  getNumberPoolForEditingQueryOptions,
  useGetNumberPoolForEditing,
} from "@/entities/resource-manager/ui/queries/get-number-pool-for-editing.query";
import type { NumberAttributeParameters } from "@/entities/schema/domain/model/schema";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

interface NumberPoolFormProps {
  currentObject?: ObjectFormProps["currentObject"];
  onCancel?: ObjectFormProps["onCancel"];
  onSuccess?: ObjectFormProps["onSuccess"];
}

function useRangeLimits(kind?: string | null, attributeName?: string | null): RangeLimits | null {
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const attribute = [...generics, ...nodes]
    .find((schema) => schema.kind === kind)
    ?.attributes?.find(({ name }) => name === attributeName);
  if (!attribute) return null;

  const parameters = attribute.parameters as NumberAttributeParameters | undefined;
  return { attribute: attribute.name, min: parameters?.min_value, max: parameters?.max_value };
}

function toFieldValue(value: string) {
  return value ? { source: { type: "user" }, value } : DEFAULT_FORM_FIELD_VALUE;
}

function toPoolFields(pool: NumberPoolForEditing) {
  return { name: { value: pool.name }, description: { value: pool.description } };
}

export const NumberPoolForm = ({ currentObject, ...props }: NumberPoolFormProps) => {
  const poolId = typeof currentObject?.id === "string" ? currentObject.id : "";
  const { data: initialPool, isPending } = useGetNumberPoolForEditing(
    { poolId },
    { enabled: !!poolId }
  );

  if (!poolId) return <NumberPoolFormContent {...props} />;
  if (isPending) return <LoadingIndicator className="p-4" />;
  if (!initialPool) {
    return <Alert type={ALERT_TYPES.ERROR} message="Unable to load the number pool" />;
  }

  return <NumberPoolFormContent initialPool={initialPool} {...props} />;
};

interface NumberPoolFormContentProps extends Omit<NumberPoolFormProps, "currentObject"> {
  initialPool?: NumberPoolForEditing;
}

const NumberPoolFormContent = ({
  initialPool,
  onSuccess,
  onCancel,
}: NumberPoolFormContentProps) => {
  const { currentBranch } = useCurrentBranch();
  const queryClient = useQueryClient();
  const createObject = useCreateObjectMutation();
  const updateObject = useUpdateObjectMutation();
  const applyRangeChanges = useApplyNumberPoolRangeChangesMutation();

  const [createdPool, setCreatedPool] = useState<NodeCore | null>(null);
  const [rangeSaveError, setRangeSaveError] = useState<string | null>(null);
  const poolId = initialPool?.id ?? createdPool?.id;
  const { data: storedPool } = useGetNumberPoolForEditing(
    { poolId: poolId ?? "" },
    { enabled: !!poolId }
  );

  // Default values are read once at mount, so a background refetch of the pool never resets the rows being typed.
  const form = useForm<FieldValues>({
    defaultValues: {
      name: initialPool ? toFieldValue(initialPool.name) : DEFAULT_FORM_FIELD_VALUE,
      description: initialPool ? toFieldValue(initialPool.description) : DEFAULT_FORM_FIELD_VALUE,
      [RANGES_FIELD]: initialPool ? toRangeRows(initialPool.ranges) : [{ ...EMPTY_RANGE_ROW }],
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

  function getPoolOptions(id: string) {
    return getNumberPoolForEditingQueryOptions({ branchName: currentBranch.name, poolId: id });
  }

  /** Returns `false` when the server refused a range; the form then stays open with the rows linked to what was applied. */
  async function saveRanges(
    pool: NodeCore,
    stored: StoredRange[],
    data: FieldValues,
    successMessage: string
  ): Promise<boolean> {
    const rows: RangeRow[] = data[RANGES_FIELD];
    const changes = diffRanges(stored, rows);
    const { errorMessage } = hasRangeChanges(changes)
      ? await applyRangeChanges.mutateAsync({ poolId: pool.id, changes })
      : { errorMessage: null };

    if (errorMessage === null) {
      setRangeSaveError(null);
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={successMessage} />, {
        toastId: "alert-success-number-pool-save",
      });
      await onSuccess?.(pool);
      return true;
    }

    setRangeSaveError(errorMessage);
    const refreshed = await queryClient.fetchQuery({ ...getPoolOptions(pool.id), staleTime: 0 });
    // The form resets to the submitted values once this handler returns, so the linked rows go into that object.
    data[RANGES_FIELD] = matchRowsToStored(rows, refreshed.ranges);
    return false;
  }

  async function createPool(data: FieldValues) {
    const {
      [RANGES_FIELD]: _rows,
      [NUMBER_POOL_ALLOCATION_SCOPE_FIELD]: scope = [],
      ...poolFields
    } = data;
    if (createdPool) {
      const { ranges } = await queryClient.ensureQueryData(getPoolOptions(createdPool.id));
      await saveRanges(createdPool, ranges, data, "Number pool created");
      return;
    }

    // A refused pool is already reported by the API layer's notification, and the form stays open.
    const pool = await createObject
      .mutateAsync({
        objectKind: NUMBER_POOL_KIND,
        data: {
          ...getCreateMutationFromFormDataOnly(poolFields),
          ...(scope.length > 0 && { [NUMBER_POOL_ALLOCATION_SCOPE_FIELD]: { value: scope } }),
        },
      })
      .catch(() => null);
    if (!pool) return;

    const isSaved = await saveRanges(pool, [], data, "Number pool created");
    if (!isSaved) setCreatedPool(pool);
  }

  async function updatePool(data: FieldValues) {
    if (!initialPool) return;

    const { [RANGES_FIELD]: _rows, ...poolFields } = data;
    const stored = await queryClient.ensureQueryData(getPoolOptions(initialPool.id));
    const changedFields = getCreateMutationFromFormDataOnly(poolFields, toPoolFields(stored));
    const pool: NodeCore = {
      id: stored.id,
      display_label: stored.name,
      __typename: NUMBER_POOL_KIND,
    };

    if (Object.keys(changedFields).length > 0) {
      // A refused pool update is already reported by the API layer's notification.
      const updatedPool = await updateObject
        .mutateAsync({ objectKind: NUMBER_POOL_KIND, data: { id: stored.id, ...changedFields } })
        .catch(() => null);
      if (!updatedPool) return;
    }

    await saveRanges(pool, stored.ranges, data, "Number pool updated");
  }

  return (
    <div className="flex flex-1 flex-col overflow-auto bg-content">
      <Form form={form} onSubmit={initialPool ? updatePool : createPool}>
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
          <AllocatesBlock variant="input" scopeField={<ScopeField />} />
        )}

        {rangeSaveError && <Alert type={ALERT_TYPES.ERROR} message={rangeSaveError} />}
        <RangesField limits={rangeLimits} />

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
