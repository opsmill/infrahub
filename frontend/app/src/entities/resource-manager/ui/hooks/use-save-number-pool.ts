import { useQueryClient } from "@tanstack/react-query";
import { createElement, useState } from "react";
import type { FieldValues } from "react-hook-form";
import { toast } from "react-toastify";

import type { ObjectFormProps } from "@/shared/components/form/object-form";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

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
  RANGES_FIELD,
} from "@/entities/resource-manager/domain/model/pool";
import {
  diffRanges,
  hasRangeChanges,
  matchRowsToStored,
} from "@/entities/resource-manager/domain/rules/plan-range-changes";
import { useApplyNumberPoolRangeChangesMutation } from "@/entities/resource-manager/ui/queries/apply-number-pool-range-changes.mutation";
import { getNumberPoolForEditingQueryOptions } from "@/entities/resource-manager/ui/queries/get-number-pool-for-editing.query";

interface UseSaveNumberPoolParams {
  initialPool?: NumberPoolForEditing;
  onSuccess?: ObjectFormProps["onSuccess"];
}

function toPoolFields(pool: NumberPoolForEditing) {
  return { name: { value: pool.name }, description: { value: pool.description } };
}

export function useSaveNumberPool({ initialPool, onSuccess }: UseSaveNumberPoolParams) {
  const { currentBranch } = useCurrentBranch();
  const queryClient = useQueryClient();
  const createObject = useCreateObjectMutation();
  const updateObject = useUpdateObjectMutation();
  const applyRangeChanges = useApplyNumberPoolRangeChangesMutation();

  const [createdPool, setCreatedPool] = useState<NodeCore | null>(null);
  const [rangeSaveError, setRangeSaveError] = useState<string | null>(null);
  const isSchemaPool = initialPool?.poolType === "Schema";

  function getPoolOptions(poolId: string) {
    return getNumberPoolForEditingQueryOptions({ branchName: currentBranch.name, poolId });
  }

  /** Resolves to `null` once saved, or to the rows linked to the stored ranges when the server refused a range. */
  async function saveRanges(
    pool: NodeCore,
    stored: StoredRange[],
    rows: RangeRow[],
    successMessage: string
  ): Promise<RangeRow[] | null> {
    const changes = diffRanges(stored, rows);
    const { errorMessage } =
      !isSchemaPool && hasRangeChanges(changes)
        ? await applyRangeChanges.mutateAsync({ poolId: pool.id, changes })
        : { errorMessage: null };

    if (errorMessage === null) {
      setRangeSaveError(null);
      toast(createElement(Alert, { type: ALERT_TYPES.SUCCESS, message: successMessage }), {
        toastId: "alert-success-number-pool-save",
      });
      await onSuccess?.(pool);
      return null;
    }

    setRangeSaveError(errorMessage);
    const refreshed = await queryClient.fetchQuery({ ...getPoolOptions(pool.id), staleTime: 0 });
    return matchRowsToStored(rows, refreshed.ranges);
  }

  async function createPool(data: FieldValues): Promise<RangeRow[] | null> {
    const {
      [RANGES_FIELD]: rows,
      [NUMBER_POOL_ALLOCATION_SCOPE_FIELD]: scope = [],
      ...poolFields
    } = data;
    if (createdPool) {
      const { ranges } = await queryClient.ensureQueryData(getPoolOptions(createdPool.id));
      return saveRanges(createdPool, ranges, rows, "Number pool created");
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
    if (!pool) return null;

    const linkedRows = await saveRanges(pool, [], rows, "Number pool created");
    if (linkedRows) setCreatedPool(pool);
    return linkedRows;
  }

  async function updatePool(pool: NumberPoolForEditing, data: FieldValues) {
    const { [RANGES_FIELD]: rows, ...poolFields } = data;
    const stored = await queryClient.ensureQueryData(getPoolOptions(pool.id));
    const changedFields = getCreateMutationFromFormDataOnly(poolFields, toPoolFields(stored));

    if (Object.keys(changedFields).length > 0) {
      // A refused pool update is already reported by the API layer's notification.
      const updatedPool = await updateObject
        .mutateAsync({ objectKind: NUMBER_POOL_KIND, data: { id: stored.id, ...changedFields } })
        .catch(() => null);
      if (!updatedPool) return null;
    }

    const storedNode: NodeCore = {
      id: stored.id,
      display_label: stored.name,
      __typename: NUMBER_POOL_KIND,
    };
    return saveRanges(storedNode, stored.ranges, rows, "Number pool updated");
  }

  /** Resolves to the values the form resets to, so rows created before a refusal stay linked to their range. */
  async function save(data: FieldValues): Promise<FieldValues | undefined> {
    const linkedRows = initialPool ? await updatePool(initialPool, data) : await createPool(data);
    return linkedRows ? { ...data, [RANGES_FIELD]: linkedRows } : undefined;
  }

  return { poolId: initialPool?.id ?? createdPool?.id, rangeSaveError, save };
}
