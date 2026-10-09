import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FieldValues } from "react-hook-form";
import { toast } from "react-toastify";

import type { ObjectFormProps } from "@/shared/components/form/object-form";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import type { FormSubmitResult } from "@/shared/components/ui/form";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import type { NumberPoolForEditing } from "@/entities/resource-manager/domain/model/number-pool";
import type {
  RangeRow,
  StoredRange,
} from "@/entities/resource-manager/domain/model/number-pool-range";
import {
  NUMBER_POOL_ALLOCATION_SCOPE_FIELD,
  NUMBER_POOL_KIND,
  NUMBER_POOL_RANGES_FIELD,
} from "@/entities/resource-manager/domain/model/pool";
import {
  diffRanges,
  getLinkedRangeIds,
  hasRangeChanges,
  linkRowsToStoredRanges,
} from "@/entities/resource-manager/domain/rules/plan-range-changes";
import { useApplyNumberPoolRangeChangesMutation } from "@/entities/resource-manager/ui/queries/apply-number-pool-range-changes.mutation";
import { getNumberPoolForEditingQueryOptions } from "@/entities/resource-manager/ui/queries/get-number-pool-for-editing.query";

const POOL_UNREADABLE_MESSAGE = "The number pool could not be read. It may have been deleted.";

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

  const [createdPoolId, setCreatedPoolId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [knownRangeIds, setKnownRangeIds] = useState<ReadonlySet<string>>(
    () => new Set(initialPool?.ranges.map(({ id }) => id))
  );
  const poolId = initialPool?.id ?? createdPoolId ?? undefined;
  const isSchemaPool = initialPool?.poolType === "Schema";

  function fetchStoredPool(id: string) {
    return queryClient.fetchQuery({
      ...getNumberPoolForEditingQueryOptions({ branchName: currentBranch.name, poolId: id }),
      staleTime: 0,
    });
  }

  /** Resolves to `null` once saved, or to the rows to keep in the form when the server refused a range. */
  async function saveRanges(
    pool: NodeCore,
    stored: StoredRange[],
    rows: RangeRow[],
    successMessage: string
  ): Promise<RangeRow[] | null> {
    const changes = diffRanges(stored, linkRowsToStoredRanges(rows, stored), knownRangeIds);
    const { errorMessage } =
      !isSchemaPool && hasRangeChanges(changes)
        ? await applyRangeChanges.mutateAsync({ poolId: pool.id, changes })
        : { errorMessage: null };

    if (errorMessage === null) {
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={successMessage} />, {
        toastId: "alert-success-number-pool-save",
      });
      await onSuccess?.(pool);
      return null;
    }

    setSaveError(errorMessage);
    // Rows left unlinked here are linked on the next save, which reads the stored ranges again.
    const refreshed = await fetchStoredPool(pool.id).catch(() => null);
    const keptRows = refreshed ? linkRowsToStoredRanges(rows, refreshed.ranges) : rows;
    setKnownRangeIds((known) => new Set([...known, ...getLinkedRangeIds(keptRows)]));
    return keptRows;
  }

  async function createPool(data: FieldValues): Promise<RangeRow[] | null> {
    const {
      [NUMBER_POOL_RANGES_FIELD]: rows,
      [NUMBER_POOL_ALLOCATION_SCOPE_FIELD]: scope = [],
      ...poolFields
    } = data;

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

    setCreatedPoolId(pool.id);
    return saveRanges(pool, [], rows, "Number pool created");
  }

  async function updatePool(id: string, data: FieldValues): Promise<RangeRow[] | null> {
    const { [NUMBER_POOL_RANGES_FIELD]: rows, name, description } = data;
    const stored = await fetchStoredPool(id).catch(() => null);
    if (!stored) {
      setSaveError(POOL_UNREADABLE_MESSAGE);
      return null;
    }

    const changedFields = getCreateMutationFromFormDataOnly(
      { name, description },
      toPoolFields(stored)
    );
    let pool: NodeCore = {
      id: stored.id,
      display_label: stored.name,
      __typename: NUMBER_POOL_KIND,
    };

    if (Object.keys(changedFields).length > 0) {
      // A refused pool update is already reported by the API layer's notification.
      const updatedPool = await updateObject
        .mutateAsync({ objectKind: NUMBER_POOL_KIND, data: { id: stored.id, ...changedFields } })
        .catch(() => null);
      if (!updatedPool) return null;
      pool = updatedPool;
    }

    const successMessage = initialPool ? "Number pool updated" : "Number pool created";
    return saveRanges(pool, stored.ranges, rows, successMessage);
  }

  /** Resolves to the values the form resets to, so rows created before a refusal stay linked to their range. */
  async function save(data: FieldValues): Promise<FormSubmitResult | undefined> {
    setSaveError(null);
    const keptRows = poolId ? await updatePool(poolId, data) : await createPool(data);
    return keptRows ? { resetTo: { ...data, [NUMBER_POOL_RANGES_FIELD]: keptRows } } : undefined;
  }

  return { poolId, saveError, save };
}
