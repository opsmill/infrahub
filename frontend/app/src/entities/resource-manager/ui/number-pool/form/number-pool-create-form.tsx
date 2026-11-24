import { useForm } from "react-hook-form";
import { toast } from "react-toastify";

import type { CoreNumberPoolCreateInput } from "@/shared/api/graphql/generated/types";
import type { NodeFormProps } from "@/shared/components/form/node-form";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { NUMBER_POOL_KIND } from "@/entities/resource-manager/domain/model/pool";
import type { NumberPoolFormData } from "@/entities/resource-manager/ui/number-pool/form/number-pool-form";
import { NumberPoolForm } from "@/entities/resource-manager/ui/number-pool/form/number-pool-form";
import { createRangeRow } from "@/entities/resource-manager/ui/number-pool/form/number-pool-ranges-input";

export interface NumberPoolCreateFormProps extends Pick<NodeFormProps, "onSuccess" | "onCancel"> {}

export function NumberPoolCreateForm({ onSuccess, onCancel }: NumberPoolCreateFormProps) {
  const createObject = useCreateObjectMutation();
  const form = useForm<NumberPoolFormData>({
    defaultValues: {
      name: { value: "" },
      description: { value: null },
      node: { value: "" },
      node_attribute: { value: "" },
      allocation_scope: { value: [] },
      ranges: [createRangeRow()],
    },
  });

  const onSubmit = async (values: NumberPoolFormData) => {
    await createObject.mutateAsync(
      {
        objectKind: NUMBER_POOL_KIND,
        data: values satisfies CoreNumberPoolCreateInput,
        processErrorMessage: (message) => form.setError("root.server", { type: "server", message }),
      },
      {
        onSuccess: async (pool) => {
          toast(<Alert type={ALERT_TYPES.SUCCESS} message="Number pool created" />, {
            toastId: "alert-success-number-pool-create",
          });
          await onSuccess?.(pool);
        },
      }
    );
  };

  return <NumberPoolForm form={form} onSubmit={onSubmit} onCancel={onCancel} />;
}
