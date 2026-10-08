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
import { getCurrentFieldValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import type { RangeRow } from "@/entities/resource-manager/domain/model/number-pool-range";
import {
  NUMBER_POOL_KIND,
  NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
  NUMBER_POOL_NODE_FIELD,
} from "@/entities/resource-manager/domain/model/pool";
import {
  diffRanges,
  matchRowsToStored,
} from "@/entities/resource-manager/domain/rules/plan-range-changes";
import type { RangeLimits } from "@/entities/resource-manager/domain/rules/validate-range-rows";
import { AllocatesBlock } from "@/entities/resource-manager/ui/number-pool-form/allocates-block";
import {
  EMPTY_RANGE_ROW,
  RANGES_FIELD,
  RangesField,
} from "@/entities/resource-manager/ui/number-pool-form/ranges-field";
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

export const NumberPoolForm = ({ currentObject, onSuccess, onCancel }: NumberPoolFormProps) => {
  const { currentBranch } = useCurrentBranch();
  const queryClient = useQueryClient();
  const createObject = useCreateObjectMutation();
  const updateObject = useUpdateObjectMutation();
  const applyRangeChanges = useApplyNumberPoolRangeChangesMutation();

  const [createdPool, setCreatedPool] = useState<NodeCore | null>(null);
  const [rangeSaveError, setRangeSaveError] = useState<string | null>(null);
  const currentPoolId = typeof currentObject?.id === "string" ? currentObject.id : undefined;
  const poolId = currentPoolId ?? createdPool?.id;
  const { data: storedPool } = useGetNumberPoolForEditing(
    { poolId: poolId ?? "" },
    { enabled: !!poolId }
  );

  const form = useForm<FieldValues>({
    defaultValues: {
      name: getCurrentFieldValue("name", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
      description: getCurrentFieldValue("description", currentObject) ?? DEFAULT_FORM_FIELD_VALUE,
      [RANGES_FIELD]: currentObject ? [] : [{ ...EMPTY_RANGE_ROW }],
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

  async function saveRanges(pool: NodeCore, rows: RangeRow[], data: FieldValues) {
    const poolOptions = getNumberPoolForEditingQueryOptions({
      branchName: currentBranch.name,
      poolId: pool.id,
    });
    const stored = createdPool ? (await queryClient.fetchQuery(poolOptions)).ranges : [];
    const { errorMessage } = await applyRangeChanges.mutateAsync({
      poolId: pool.id,
      changes: diffRanges(stored, rows),
    });

    if (errorMessage === null) {
      setRangeSaveError(null);
      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Number pool created" />, {
        toastId: "alert-success-number-pool-create",
      });
      await onSuccess?.(pool);
      return;
    }

    setCreatedPool(pool);
    setRangeSaveError(errorMessage);
    const refreshed = await queryClient.fetchQuery(poolOptions);
    // The form resets to the submitted values once this handler returns, so the linked rows go into that object.
    data[RANGES_FIELD] = matchRowsToStored(rows, refreshed.ranges);
  }

  async function createPool(data: FieldValues) {
    const { [RANGES_FIELD]: rows, ...poolFields } = data;
    if (createdPool) {
      await saveRanges(createdPool, rows, data);
      return;
    }

    // A refused pool is already reported by the API layer's notification, and the form stays open.
    const pool = await createObject
      .mutateAsync({
        objectKind: NUMBER_POOL_KIND,
        data: getCreateMutationFromFormDataOnly(poolFields),
      })
      .catch(() => null);
    if (!pool) return;

    await saveRanges(pool, rows, data);
  }

  async function updatePool(data: FieldValues) {
    const { [RANGES_FIELD]: _rows, ...poolFields } = data;
    const newObject = getCreateMutationFromFormDataOnly(poolFields, currentObject);
    if (!currentObject || !Object.keys(newObject).length) return;

    await updateObject.mutateAsync(
      { objectKind: NUMBER_POOL_KIND, data: { id: currentObject.id, ...newObject } },
      {
        onSuccess: async (updatedNode) => {
          toast(<Alert type={ALERT_TYPES.SUCCESS} message="Number pool updated" />, {
            toastId: "alert-success-number-pool-update",
          });
          await onSuccess?.(updatedNode);
        },
      }
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-auto bg-content">
      <Form form={form} onSubmit={currentObject ? updatePool : createPool}>
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

        {rangeSaveError && <Alert type={ALERT_TYPES.ERROR} message={rangeSaveError} />}
        {!currentObject && <RangesField limits={rangeLimits} />}

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
