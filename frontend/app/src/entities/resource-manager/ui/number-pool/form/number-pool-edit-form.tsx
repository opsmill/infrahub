import { useForm } from "react-hook-form";
import { toast } from "react-toastify";

import type { CoreNumberPoolUpdateInput } from "@/shared/api/graphql/generated/types";
import ErrorScreen from "@/shared/components/errors/error-screen";
import type { NodeFormProps } from "@/shared/components/form/node-form";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import { NUMBER_POOL_KIND } from "@/entities/resource-manager/domain/model/pool";
import type { NumberPoolFormData } from "@/entities/resource-manager/ui/number-pool/form/number-pool-form";
import { NumberPoolForm } from "@/entities/resource-manager/ui/number-pool/form/number-pool-form";
import { useGetNumberPool } from "@/entities/resource-manager/ui/queries/get-number-pool.query";

export interface NumberPoolEditFormProps extends Pick<NodeFormProps, "onSuccess" | "onCancel"> {
  poolId: string;
}

export function NumberPoolEditForm({ poolId, onSuccess, onCancel }: NumberPoolEditFormProps) {
  const { data: pool, isPending, error } = useGetNumberPool(poolId);
  const updateObject = useUpdateObjectMutation();
  const form = useForm<NumberPoolFormData>({
    values: pool,
    resetOptions: { keepDirtyValues: true },
  });

  if (isPending) return <LoadingIndicator className="mt-4" />;

  if (error) return <ErrorScreen message={error.message} />;

  const onSubmit = async (values: NumberPoolFormData) => {
    await updateObject.mutateAsync(
      {
        objectKind: NUMBER_POOL_KIND,
        data: {
          id: poolId,
          name: values.name,
          description: values.description,
          ranges: values.ranges,
        } satisfies CoreNumberPoolUpdateInput,
        processErrorMessage: (message) => form.setError("root.server", { type: "server", message }),
      },
      {
        onSuccess: async (updatedPool) => {
          toast(<Alert type={ALERT_TYPES.SUCCESS} message="Number pool updated" />, {
            toastId: "alert-success-number-pool-update",
          });
          await onSuccess?.(updatedPool);
        },
      }
    );
  };

  return <NumberPoolForm form={form} onSubmit={onSubmit} onCancel={onCancel} isUpdate />;
}
